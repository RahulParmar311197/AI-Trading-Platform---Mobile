import pytest

from app.broker_adapter import BrokerOrderRequest
from app.dhan_adapter import DhanAdapter, DhanConfig, DhanHttpTransport


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.status_code = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self, placement_status="TRANSIT", filled_qty=None, average_price=None):
        self.calls = []
        self.placement_status = placement_status
        self.filled_qty = filled_qty
        self.average_price = average_price
        self.external_order = {"orderId": "D123", "orderStatus": "TRANSIT", "correlationId": "TEST123"}

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        payload = {"orderId": "D123", "orderStatus": self.placement_status}
        if self.filled_qty is not None:
            payload["filledQty"] = self.filled_qty
        if self.average_price is not None:
            payload["averageTradedPrice"] = self.average_price
        return FakeResponse(payload)

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return FakeResponse({"orderId": "D123", "orderStatus": "CANCELLED"})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if "/orders/external/" in url:
            return FakeResponse(self.external_order)
        return FakeResponse([])


def request(client_order_id="TEST123"):
    return BrokerOrderRequest(client_order_id=client_order_id, security_id="11536", exchange_segment="NSE_EQ", side="BUY", quantity=5, order_type="MARKET", product_type="INTRADAY", validity="DAY", price=0, trigger_price=0)


def test_live_is_disabled_by_default():
    adapter = DhanAdapter(DhanConfig("client", "token"), FakeTransport())
    with pytest.raises(RuntimeError, match="DHAN_LIVE_ENABLED"):
        adapter.submit_order(request())


def test_submit_maps_dhan_v2_request_and_correlation_id():
    transport = FakeTransport()
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.submit_order(request())
    assert result.order_id == "D123"
    assert result.status == "NEW"
    method, url, kwargs = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/orders")
    assert kwargs["headers"]["access-token"] == "token"
    assert kwargs["json"]["dhanClientId"] == "client"
    assert kwargs["json"]["securityId"] == "11536"
    assert kwargs["json"]["correlationId"] == "TEST123"


def test_submit_maps_dhan_part_traded_to_partial_fill():
    transport = FakeTransport(placement_status="PART_TRADED", filled_qty=2, average_price=101.5)
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.submit_order(request())
    assert result.order_id == "D123"
    assert result.status == "PARTIALLY_FILLED"
    assert result.filled_quantity == 2
    assert result.average_price == 101.5


def test_submit_rejects_part_traded_without_fill_quantity():
    transport = FakeTransport(placement_status="PART_TRADED", average_price=101.5)
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    with pytest.raises(ValueError, match="filled broker status requires positive filled quantity"):
        adapter.submit_order(request())


def test_cancel_maps_dhan_response():
    transport = FakeTransport()
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.cancel_order("D123")
    assert result.order_id == "D123"
    assert result.status == "CANCELLED"
    assert transport.calls[0][0] == "DELETE"


def test_find_order_by_client_id_uses_dhan_external_lookup():
    transport = FakeTransport()
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.find_order_by_client_id("TEST123")
    assert result["orderId"] == "D123"
    method, url, kwargs = transport.calls[0]
    assert method == "GET"
    assert url.endswith("/orders/external/TEST123")
    assert kwargs["headers"]["access-token"] == "token"


def test_find_order_by_client_id_rejects_overlong_correlation_id():
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), FakeTransport())
    with pytest.raises(ValueError, match="30 characters"):
        adapter.find_order_by_client_id("X" * 31)


def test_credentials_are_required_before_transport():
    adapter = DhanAdapter(DhanConfig("", "", live_enabled=True), FakeTransport())
    with pytest.raises(RuntimeError, match="credentials"):
        adapter.submit_order(request())


def test_dhan_http_transport_passes_bounded_timeout():
    class FakeHttpClient:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return FakeResponse({"ok": True})

        def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            return FakeResponse({"ok": True})

        def delete(self, url, **kwargs):
            self.calls.append(("DELETE", url, kwargs))
            return FakeResponse({"ok": True})

        def close(self):
            pass

    client = FakeHttpClient()
    transport = DhanHttpTransport(timeout_seconds=7.5, client=client)
    transport.post("https://example.test/orders")
    transport.get("https://example.test/orders")
    transport.delete("https://example.test/orders/D123")
    assert all(call[2]["timeout"] == 7.5 for call in client.calls)


def test_dhan_http_transport_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="greater than zero"):
        DhanHttpTransport(timeout_seconds=0)
