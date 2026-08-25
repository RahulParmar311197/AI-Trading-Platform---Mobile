from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import BrokerOrder, OrderReconciler, ReconciliationAction


def pending_lifecycle():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("cid-1", "NIFTY", "BUY", 10)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.PENDING_RECONCILIATION)
    return lifecycle, order


def test_missing_broker_order_does_not_mutate_local_state():
    lifecycle, order = pending_lifecycle()
    events = OrderReconciler(lifecycle).reconcile([])
    assert lifecycle.orders[order.order_id].status == OrderStatus.PENDING_RECONCILIATION
    assert events == []


def test_broker_open_order_resolves_pending_state():
    lifecycle, order = pending_lifecycle()
    remote = BrokerOrder("broker-1", "NIFTY", "BUY", 10, OrderStatus.SUBMITTED, client_order_id=order.order_id)
    events = OrderReconciler(lifecycle).reconcile([remote])
    assert lifecycle.orders[order.order_id].status == OrderStatus.SUBMITTED
    assert events[0].action == ReconciliationAction.UPDATE


def test_broker_partial_fill_reconciles_quantity():
    lifecycle, order = pending_lifecycle()
    remote = BrokerOrder("broker-2", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, order.order_id)
    OrderReconciler(lifecycle).reconcile([remote])
    assert lifecycle.orders[order.order_id].status == OrderStatus.PARTIALLY_FILLED
    assert lifecycle.orders[order.order_id].filled_quantity == 4


def test_identity_mismatch_is_alerted_without_mutation():
    lifecycle, order = pending_lifecycle()
    remote = BrokerOrder("broker-3", "BANKNIFTY", "BUY", 10, OrderStatus.SUBMITTED, client_order_id=order.order_id)
    events = OrderReconciler(lifecycle).reconcile([remote])
    assert lifecycle.orders[order.order_id].status == OrderStatus.PENDING_RECONCILIATION
    assert events[0].action == ReconciliationAction.ALERT
    assert "SYMBOL_MISMATCH" in events[0].reason


def test_duplicate_broker_snapshot_is_alerted_not_applied_twice():
    lifecycle, order = pending_lifecycle()
    remote = BrokerOrder("broker-4", "NIFTY", "BUY", 10, OrderStatus.SUBMITTED, client_order_id=order.order_id)
    events = OrderReconciler(lifecycle).reconcile([remote, remote])
    assert lifecycle.orders[order.order_id].status == OrderStatus.SUBMITTED
    assert events[1].action == ReconciliationAction.ALERT
