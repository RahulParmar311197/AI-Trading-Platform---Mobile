import pytest

from app.authoritative_cancel import AuthoritativeCancelReconciler
from app.broker_adapter import BrokerOrderStatus


class Order:
    client_order_id = "client-1"
    broker_order_id = "broker-1"
    broker_account_id = "001"
    broker_route = "upstox:account:001"


class Router:
    def __init__(self, post_cancel_status):
        self.post_cancel_status = post_cancel_status
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
            "status": self.post_cancel_status,
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 1,
            "filled_quantity": 1 if self.post_cancel_status == BrokerOrderStatus.FILLED.value else 0,
            "average_price": 101.5 if self.post_cancel_status == BrokerOrderStatus.FILLED.value else None,
            "broker_account_id": "001",
            "broker_route": "upstox:account:001",
        }


def test_post_cancel_filled_wins_cancel_fill_race():
    router = Router(BrokerOrderStatus.FILLED.value)

    result = AuthoritativeCancelReconciler().cancel_and_reconcile(router, Order())

    assert result.source == "post_cancel_get_order"
    assert result.update.status == BrokerOrderStatus.FILLED.value
    assert result.update.filled_quantity == 1
    assert result.update.average_price == 101.5
    assert router.cancel_calls == [("broker-1", "upstox:account:001", "001")]
    assert router.get_calls == [("broker-1", "upstox:account:001")]


def test_post_cancel_cancelled_is_accepted_only_after_authoritative_read():
    router = Router(BrokerOrderStatus.CANCELLED.value)

    result = AuthoritativeCancelReconciler().cancel_and_reconcile(router, Order())

    assert result.update.status == BrokerOrderStatus.CANCELLED.value


def test_post_cancel_non_terminal_state_fails_closed():
    router = Router("OPEN")

    with pytest.raises(RuntimeError, match="not terminal"):
        AuthoritativeCancelReconciler().cancel_and_reconcile(router, Order())


def test_post_cancel_read_failure_fails_closed():
    class FailingRouter(Router):
        def get_order(self, order_id, *, route=None):
            raise TimeoutError("broker timeout")

    with pytest.raises(RuntimeError, match="reconciliation required"):
        AuthoritativeCancelReconciler().cancel_and_reconcile(FailingRouter("OPEN"), Order())
