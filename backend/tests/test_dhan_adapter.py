import pytest

from app.broker_adapter import BrokerOrderRequest
from app.dhan_adapter import DhanAdapter, DhanConfig


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"orderId": "D123", "orderStatus": "TRANSIT"})

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return FakeResponse({"orderId": "D123", "orderStatus": "CANCELLED"})


def request():
    return BrokerOrderRequest(
        client_order_id="TEST123",
        security_id="11536",
        exchange_segment="NSE_EQ",
        side="BUY",
        quantity=5,
        order_type="MARKET",
        product_type="INTRADAY",
        validity="DAY",
        price=0,
        trigger_price=0,
    )


def test_live_is_disabled_by_default():
    adapter = DhanAdapter(DhanConfig("client", "token"), FakeTransport())
    with pytest.raises(RuntimeError, match="DHAN_LIVE_ENABLED"):
        adapter.submit_order(request())


def test_submit_maps_dhan_v2_request():
    transport = FakeTransport()
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.submit_order(request())
    assert result.order_id == "D123"
    assert result.status == "TRANSIT"
    method, url, kwargs = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/orders")
    assert kwargs["headers"]["access-token"] == "token"
    assert kwargs["json"]["dhanClientId"] == "client"
    assert kwargs["json"]["securityId"] == "11536"


def test_cancel_maps_dhan_response():
    transport = FakeTransport()
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=True), transport)
    result = adapter.cancel_order("D123")
    assert result.order_id == "D123"
    assert result.status == "CANCELLED"
    assert transport.calls[0][0] == "DELETE"


def test_credentials_are_required_before_transport():
    adapter = DhanAdapter(DhanConfig("", "", live_enabled=True), FakeTransport())
    with pytest.raises(RuntimeError, match="credentials"):
        adapter.submit_order(request())
