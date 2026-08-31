from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciliationService
from app.startup_order_recovery import StartupOrderRecovery


class FakeBroker:
    def __init__(self, orders):
        self.orders = orders

    def find_order(self, order_id, route=None):
        return self.orders.get(order_id)


class GetOrderBroker:
    def __init__(self, order):
        self.order = order
        self.requested = []

    def get_order(self, order_id, route=None):
        self.requested.append((order_id, route))
        return self.order


def make_pending():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("cid-1", "NIFTY", "BUY", 10)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.PENDING_RECONCILIATION)
    return lifecycle


def test_startup_is_ready_when_pending_order_is_recovered():
    lifecycle = make_pending()
    broker = FakeBroker({"cid-1": {"order_id": "broker-1", "status": "OPEN", "filled_quantity": 0}})
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


def test_startup_single_order_recovery_supports_router_style_get_order():
    lifecycle = make_pending()
    broker = GetOrderBroker({
        "order_id": "broker-1",
        "status": "FILLED",
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 10,
        "filled_quantity": 10,
        "average_fill_price": 250.5,
        "client_order_id": "cid-1",
    })
    result = StartupOrderRecovery(OrderReconciliationService(broker)).run(lifecycle)
    assert result.ready is True
    assert broker.requested == [("cid-1", None)]
    assert lifecycle.orders["cid-1"].status == OrderStatus.FILLED
    assert lifecycle.orders["cid-1"].filled_quantity == 10
    assert lifecycle.orders["cid-1"].average_fill_price == 250.5


def test_startup_recovery_rejects_malformed_authoritative_order():
    lifecycle = make_pending()
    broker = FakeBroker({"cid-1": {"status": "FILLED", "filled_quantity": 10}})
    result = StartupOrderRecovery(OrderReconciliationService(broker)).run(lifecycle)
    assert result.ready is False
    assert result.pending_after == 1
    assert result.unresolved_order_ids == ("cid-1",)
    assert lifecycle.orders["cid-1"].status == OrderStatus.PENDING_RECONCILIATION
