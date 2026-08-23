import pytest

from app.broker_adapter import BrokerOrderRequest
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig, UpstoxHttpTransport


class Response:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.data


class Transport:
    def __init__(self):
        self.calls = []
        self.next_response = Response({"data": {"order_ids": ["U1"]}})

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.next_response


def req(tag="client-1", order_type="MARKET"):
    return BrokerOrderRequest(client_order_id=tag, symbol="NIFTY", side="BUY", quantity=10, order_type=order_type, price=100, security_id="NSE_EQ|TEST", product_type="INTRADAY")


def test_live_disabled_by_default():
    with pytest.raises(RuntimeError, match="UPSTOX_LIVE_ENABLED"):
        UpstoxAdapter(UpstoxConfig("token"), Transport()).submit_order(req())


def test_submit_uses_v3_tag_and_safe_market_protection():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    result = adapter.submit_order(req())
    assert result.order_id == "U1"
    method, url, kwargs = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/v3/order/place")
    assert kwargs["json"]["tag"] == "client-1"
    assert kwargs["json"]["slice"] is False
    assert kwargs["json"]["market_protection"] == -1


def test_tag_limit_is_enforced():
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), Transport())
    with pytest.raises(ValueError, match="40 characters"):
        adapter.submit_order(req("x" * 41))


def test_reconciliation_returns_single_match():
    transport = Transport()
    transport.next_response = Response({"data": [{"tag": "client-1", "order_id": "U1", "status": "complete", "filled_quantity": 10, "average_price": 100.2}]})
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    result = adapter.find_order_by_client_id("client-1")
    assert result["order_id"] == "U1"
    assert result["filled_quantity"] == 10


def test_reconciliation_preserves_multiple_matches():
    transport = Transport()
    transport.next_response = Response({"data": [{"tag": "client-1", "order_id": "U1"}, {"tag": "client-1", "order_id": "U2"}]})
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    result = adapter.find_order_by_client_id("client-1")
    assert result["multi_order"] is True
    assert [x["order_id"] for x in result["orders"]] == ["U1", "U2"]


def test_transport_rejects_invalid_timeout():
    with pytest.raises(ValueError, match="greater than zero"):
        UpstoxHttpTransport(0)
