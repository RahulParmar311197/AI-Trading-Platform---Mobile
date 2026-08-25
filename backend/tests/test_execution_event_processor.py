from app.execution_event_processor import ExecutionEvent, IdempotentExecutionEventProcessor
from app.execution_lifecycle import ExecutionLedger, OrderStatus
from app.execution_state_store import ExecutionStateStore


def test_duplicate_fill_event_is_applied_once():
    store = ExecutionStateStore()
    ledger = ExecutionLedger(state_store=store)
    order = ledger.create("NIFTY", "BUY", 10)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    processor = IdempotentExecutionEventProcessor(ledger)
    processor.process(ExecutionEvent("s1", order.order_id, "SUBMITTED"))
    assert processor.process(ExecutionEvent("f1", order.order_id, "PARTIAL_FILL", 1000, 4))
    assert processor.process(ExecutionEvent("f1", order.order_id, "PARTIAL_FILL", 1000, 4)) is False
    assert ledger.orders[order.order_id].filled_quantity == 4
    assert store.get_state().positions == {"NIFTY": 4.0}


def test_unique_events_continue_lifecycle():
    ledger = ExecutionLedger()
    order = ledger.create("NIFTY", "BUY", 2)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    processor = IdempotentExecutionEventProcessor(ledger)
    processor.process(ExecutionEvent("s2", order.order_id, "SUBMITTED"))
    processor.process(ExecutionEvent("f2", order.order_id, "FILLED", 1000, 2))
    assert ledger.orders[order.order_id].status == OrderStatus.FILLED
