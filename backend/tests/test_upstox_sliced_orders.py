import pytest

from app.broker_adapter import BrokerOrderRequest
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class Response:
    def __init__(self, data):
        self.data = data
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class Transport:
    def __init__(self, body):
        self.body = body

    def request(self, method, url, **kwargs):
        return Response(self.body)


def request():
    return BrokerOrderRequest(
        client_order_id="slice-1",
        symbol="NIFTY",
        side="BUY",
        quantity=100,
        order_type="MARKET",
        security_id="NSE_FO|TEST",
        product_type="INTRADAY",
    )


def test_multiple_upstox_order_ids_fail_closed():
    adapter = UpstoxAdapter(
        UpstoxConfig("token", live_enabled=True, slice_orders=True),
        Transport({"data": {"order_ids": ["U1", "U2"]}}),
    )
    with pytest.raises(RuntimeError, match="multiple broker order ids"):
        adapter.submit_order(request())


def test_single_upstox_order_id_remains_supported():
    adapter = UpstoxAdapter(
        UpstoxConfig("token", live_enabled=True, slice_orders=True),
        Transport({"data": {"order_ids": ["U1"]}}),
    )
    result = adapter.submit_order(request())
    assert result.order_id == "U1"
