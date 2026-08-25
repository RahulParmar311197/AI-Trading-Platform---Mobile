from app.execution_event_store import InMemoryExecutionEventStore
from app.execution_event_processor import ExecutionEvent, IdempotentExecutionEventProcessor
from app.execution_lifecycle import ExecutionLedger, OrderStatus


def test_event_store_deduplicates_event_ids():
    store = InMemoryExecutionEventStore()
    ledger = ExecutionLedger()
    order = ledger.create("NIFTY", "BUY", 1)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    processor = IdempotentExecutionEventProcessor(ledger, store)
    processor.process(ExecutionEvent("submit-1", order.order_id, "SUBMITTED"))
    assert store.contains("submit-1")
    assert processor.process(ExecutionEvent("submit-1", order.order_id, "SUBMITTED")) is False
