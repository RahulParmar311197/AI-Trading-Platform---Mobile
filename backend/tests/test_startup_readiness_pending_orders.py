from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciliationService
from app.startup_order_recovery import StartupOrderRecovery


class FakeBroker:
    def __init__(self, orders):
        self.orders = orders

    def find_order(self, order_id, route=None):
        return self.orders.get(order_id)


def make_pending(lifecycle, order_id):
    order = lifecycle.create(order_id, "NIFTY", "BUY", 10)
    lifecycle.transition(order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order_id, OrderStatus.PENDING_RECONCILIATION)
    return order


def test_unresolved_pending_order_blocks_startup_readiness():
    lifecycle = OrderLifecycle()
    make_pending(lifecycle, "cid-unresolved")

    result = StartupOrderRecovery(
        OrderReconciliationService(FakeBroker({}))
    ).run(lifecycle)

    assert result.ready is False
    assert result.pending_after == 1
    assert result.unresolved_order_ids == ("cid-unresolved",)
    assert lifecycle.orders["cid-unresolved"].status == OrderStatus.PENDING_RECONCILIATION


def test_successfully_reconciled_order_allows_startup_readiness():
    lifecycle = OrderLifecycle()
    make_pending(lifecycle, "cid-recovered")

    result = StartupOrderRecovery(
        OrderReconciliationService(
            FakeBroker({"cid-recovered": {"status": "OPEN", "filled_quantity": 0}})
        )
    ).run(lifecycle)

    assert result.ready is True
    assert result.pending_after == 0
    assert result.unresolved_order_ids == ()
    assert lifecycle.orders["cid-recovered"].status == OrderStatus.SUBMITTED
