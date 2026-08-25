from app.execution_lifecycle import ExecutionLedger, OrderStatus
from app.execution_state_store import ExecutionStateStore


def test_submitted_fill_and_cancel_sync_state_store():
    store = ExecutionStateStore()
    ledger = ExecutionLedger(state_store=store)
    order = ledger.create("NIFTY", "BUY", 10)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    ledger.transition(order.order_id, OrderStatus.SUBMITTED)
    assert store.get_state().open_order_ids == frozenset({order.order_id})
    ledger.fill(order.order_id, 1000, 4)
    assert store.get_state().positions == {"NIFTY": 4.0}
    assert order.status == OrderStatus.PARTIALLY_FILLED
    ledger.fill(order.order_id, 1001, 6)
    assert store.get_state().positions == {"NIFTY": 10.0}
    assert store.get_state().open_order_ids == frozenset()
    assert order.status == OrderStatus.FILLED


def test_rejected_order_is_removed_from_internal_open_orders():
    store = ExecutionStateStore()
    ledger = ExecutionLedger(state_store=store)
    order = ledger.create("NIFTY", "BUY", 10)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    ledger.transition(order.order_id, OrderStatus.SUBMITTED)
    ledger.transition(order.order_id, OrderStatus.REJECTED)
    assert store.get_state().open_order_ids == frozenset()
