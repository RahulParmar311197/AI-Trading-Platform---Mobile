import pytest

from app.broker_adapter import BrokerOrderRequest
from app.dhan_adapter import DhanAdapter, DhanConfig
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class DhanTransport:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"orderId": "D1", "orderStatus": "TRANSIT"})


class UpstoxTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse({"data": {"order_ids": ["U1"]}})


def order(**overrides):
    values = dict(client_order_id="test-1", symbol="NIFTY", side="BUY", quantity=1, security_id="123", exchange_segment="NSE_FNO", product_type="INTRADAY", order_type="MARKET", validity="DAY", price=0, trigger_price=None)
    values.update(overrides)
    return BrokerOrderRequest(**values)


def test_dhan_disabled_fails_before_transport():
    transport = DhanTransport()
    adapter = DhanAdapter(DhanConfig("c", "t", live_enabled=False), transport)
    with pytest.raises(RuntimeError, match="DHAN_LIVE_ENABLED"):
        adapter.submit_order(order())
    assert transport.calls == []


def test_dhan_missing_credentials_fails_before_transport():
    transport = DhanTransport()
    adapter = DhanAdapter(DhanConfig("", "", live_enabled=True), transport)
    with pytest.raises(RuntimeError, match="credentials"):
        adapter.submit_order(order())
    assert transport.calls == []


def test_dhan_valid_configuration_reaches_transport():
    transport = DhanTransport()
    adapter = DhanAdapter(DhanConfig("c", "t", live_enabled=True), transport)
    result = adapter.submit_order(order())
    assert result.order_id == "D1"
    assert len(transport.calls) == 1


def test_upstox_disabled_fails_before_transport():
    transport = UpstoxTransport()
    adapter = UpstoxAdapter(UpstoxConfig("t", live_enabled=False), transport)
    with pytest.raises(RuntimeError, match="UPSTOX_LIVE_ENABLED"):
        adapter.submit_order(order())
    assert transport.calls == []


def test_upstox_missing_token_fails_before_transport():
    transport = UpstoxTransport()
    adapter = UpstoxAdapter(UpstoxConfig("", live_enabled=True), transport)
    with pytest.raises(RuntimeError, match="access token"):
        adapter.submit_order(order())
    assert transport.calls == []


def test_upstox_valid_configuration_reaches_transport():
    transport = UpstoxTransport()
    adapter = UpstoxAdapter(UpstoxConfig("t", live_enabled=True), transport)
    result = adapter.submit_order(order(security_id="NSE_FO|123"))
    assert result.order_id == "U1"
    assert len(transport.calls) == 1
