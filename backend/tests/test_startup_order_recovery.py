from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciliationService
from app.startup_order_recovery import StartupOrderRecovery


class FakeBroker:
    def __init__(self, orders):
        self.orders = orders

    def find_order(self, order_id, route=None):
        return self.orders.get(order_id)


def make_pending():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("cid-1", "NIFTY", "BUY", 10)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.PENDING_RECONCILIATION)
    return lifecycle


def test_startup_is_ready_when_pending_order_is_recovered():
    lifecycle = make_pending()
    broker = FakeBroker({"cid-1": {"status": "OPEN", "filled_quantity": 0}})
    result = StartupOrderRecovery(OrderReconciliationService(broker)).run(lifecycle)
    assert result.ready is True
    assert result.pending_after == 0
    assert lifecycle.orders["cid-1"].status == OrderStatus.SUBMITTED


def test_startup_remains_not_ready_when_order_is_unresolved():
    lifecycle = make_pending()
    broker = FakeBroker({})
    result = StartupOrderRecovery(OrderReconciliationService(broker)).run(lifecycle)
    assert result.ready is False
    assert result.pending_after == 1
    assert result.unresolved_order_ids == ("cid-1",)
    assert lifecycle.orders["cid-1"].status == OrderStatus.PENDING_RECONCILIATION
