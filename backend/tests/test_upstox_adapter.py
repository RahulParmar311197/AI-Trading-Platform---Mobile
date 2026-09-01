import pytest

from app.broker_adapter import BrokerOrderRequest, normalize_broker_update
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


def req(tag="client-1", order_type="MARKET", **identity):
    price = None if order_type == "MARKET" else 100
    return BrokerOrderRequest(client_order_id=tag, symbol="NIFTY", side="BUY", quantity=10, order_type=order_type, price=price, security_id="NSE_EQ|TEST", product_type="INTRADAY", **identity)


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


def test_submit_rejects_fractional_quantity_before_transport_call():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    request = BrokerOrderRequest(client_order_id="client-1", symbol="NIFTY", side="BUY", quantity=10.5, security_id="NSE_EQ|TEST", product_type="INTRADAY")
    with pytest.raises(ValueError, match="quantity must be an integer"):
        adapter.submit_order(request)
    assert transport.calls == []


def test_submit_accepts_integer_quantity_and_sends_exact_quantity():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    result = adapter.submit_order(req())
    assert result.quantity == 10
    assert transport.calls[0][2]["json"]["quantity"] == 10


def test_submit_rejects_missing_security_id_before_transport_call():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    request = BrokerOrderRequest(client_order_id="client-1", symbol="NIFTY", side="BUY", quantity=10, product_type="INTRADAY")
    with pytest.raises(ValueError, match="security_id is required"):
        adapter.submit_order(request)
    assert transport.calls == []


@pytest.mark.parametrize("product_type", ["NRML", "FOO", ""])
def test_submit_rejects_unsupported_product_before_transport_call(product_type):
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    request = req(product_type=product_type)
    with pytest.raises(ValueError, match="unsupported Upstox product_type"):
        adapter.submit_order(request)
    assert transport.calls == []


@pytest.mark.parametrize("validity", ["GTC", "FOK", ""])
def test_submit_rejects_unsupported_validity_before_transport_call(validity):
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    request = req(validity=validity)
    with pytest.raises(ValueError, match="unsupported Upstox validity"):
        adapter.submit_order(request)
    assert transport.calls == []


def test_submit_rejects_unsupported_exchange_before_transport_call():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    request = req(exchange_segment="MCX_FO")
    with pytest.raises(ValueError, match="unsupported Upstox exchange_segment"):
        adapter.submit_order(request)
    assert transport.calls == []


def test_submit_accepts_supported_execution_contract():
    transport = Transport()
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    result = adapter.submit_order(req(validity="IOC", product_type="CNC", exchange_segment="NSE_EQ"))
    assert result.order_id == "U1"
    assert transport.calls[0][2]["json"]["validity"] == "IOC"
    assert transport.calls[0][2]["json"]["product"] == "D"


def test_account_bound_submit_preserves_route_identity():
    transport = Transport()
    config = UpstoxConfig("token", live_enabled=True, broker_account_id="42", broker_route="upstox:account:42", broker_route_generation="account:42:v1")
    adapter = UpstoxAdapter(config, transport)
    request = req(broker_account_id="42", broker_route="upstox:account:42", broker_route_generation="account:42:v1")
    result = adapter.submit_order(request)
    assert result.broker_account_id == "42"
    assert result.broker_route == "upstox:account:42"
    assert result.broker_route_generation == "account:42:v1"
    assert normalize_broker_update(result, expected=request) == result


def test_account_bound_submit_rejects_route_mismatch():
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True, broker_account_id="42", broker_route="upstox:account:42", broker_route_generation="account:42:v1"), Transport())
    request = req(broker_account_id="43", broker_route="upstox:account:42", broker_route_generation="account:42:v1")
    with pytest.raises(ValueError, match="broker_account_id"):
        adapter.submit_order(request)


def test_cancel_preserves_configured_account_route_identity():
    transport = Transport()
    transport.next_response = Response({"data": {"order_id": "U1", "message": "cancelled"}})
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True, broker_account_id="42", broker_route="upstox:account:42", broker_route_generation="account:42:v1"), transport)
    result = adapter.cancel_order("U1")
    assert result.status == "CANCELLED"
    assert result.broker_account_id == "42"
    assert result.broker_route == "upstox:account:42"
    assert result.broker_route_generation == "account:42:v1"


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


def test_reconciliation_fails_closed_on_multiple_matches():
    transport = Transport()
    transport.next_response = Response({"data": [{"tag": "client-1", "order_id": "U1"}, {"tag": "client-1", "order_id": "U2"}]})
    adapter = UpstoxAdapter(UpstoxConfig("token", live_enabled=True), transport)
    with pytest.raises(RuntimeError, match="ambiguous broker order identity"):
        adapter.find_order_by_client_id("client-1")


def test_transport_rejects_invalid_timeout():
    with pytest.raises(ValueError, match="greater than zero"):
        UpstoxHttpTransport(0)
