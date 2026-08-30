import pytest

from app.api.orders import _authoritative_cancel_result
from app.broker_adapter import BrokerOrderStatus


class Order:
    client_order_id = "client-1"
    broker_order_id = "broker-1"
    broker_account_id = "001"
    broker_route = "upstox:account:001"


class Router:
    def __init__(self, status):
        self.status = status
        self.cancel_calls = []
        self.get_calls = []

    def cancel(self, order_id, *, route=None, broker_account_id=None):
        self.cancel_calls.append((order_id, route, broker_account_id))
        return {"order_id": order_id, "status": "CANCEL_REQUEST_ACCEPTED"}

    def get_order(self, order_id, *, route=None):
        self.get_calls.append((order_id, route))
        return {
            "order_id": order_id,
            "client_order_id": "client-1",
            "status": self.status,
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 1,
            "filled_quantity": 1 if self.status == BrokerOrderStatus.FILLED.value else 0,
            "average_price": 101.5 if self.status == BrokerOrderStatus.FILLED.value else None,
            "broker_account_id": "001",
            "broker_route": "upstox:account:001",
        }


def test_orders_cancel_uses_authoritative_post_cancel_read():
    router = Router(BrokerOrderStatus.FILLED.value)

    result = _authoritative_cancel_result(router, Order())

    assert result.update.status == BrokerOrderStatus.FILLED.value
    assert result.update.filled_quantity == 1
    assert result.update.average_price == 101.5
    assert router.cancel_calls == [("broker-1", "upstox:account:001", "001")]
    assert router.get_calls == [("broker-1", "upstox:account:001")]


def test_orders_cancel_fails_closed_when_authoritative_read_fails():
    class FailingRouter(Router):
        def get_order(self, order_id, *, route=None):
            raise TimeoutError("broker timeout")

    with pytest.raises(RuntimeError, match="reconciliation required"):
        _authoritative_cancel_result(FailingRouter(BrokerOrderStatus.CANCELLED.value), Order())


def test_orders_cancel_never_accepts_non_terminal_post_cancel_state():
    with pytest.raises(RuntimeError, match="not terminal"):
        _authoritative_cancel_result(Router("OPEN"), Order())
