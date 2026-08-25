from app.execution_lifecycle import ExecutionLedger, OrderStatus
from app.execution_state_store import ExecutionStateStore
from app.execution_transaction_journal import ExecutionTransactionJournal
from app.journaled_execution_adapter import JournaledExecutionAdapter


def test_fill_is_journaled_and_updates_ledger(tmp_path):
    store = ExecutionStateStore()
    ledger = ExecutionLedger(state_store=store)
    order = ledger.create("NIFTY", "BUY", 10)
    ledger.transition(order.order_id, OrderStatus.RISK_APPROVED)
    ledger.transition(order.order_id, OrderStatus.SUBMITTED)
    journal = ExecutionTransactionJournal(str(tmp_path / "execution.db"))
    adapter = JournaledExecutionAdapter(ledger, journal)
    result = adapter.apply_fill(event_id="fill-1", order_id=order.order_id, price=1000, quantity=4)
    assert result.applied is True
    assert ledger.orders[order.order_id].filled_quantity == 4
    assert store.get_state().positions == {"NIFTY": 4.0}
    assert len(journal.pending_outbox()) == 1
    duplicate = adapter.apply_fill(event_id="fill-1", order_id=order.order_id, price=1000, quantity=4)
    assert duplicate.applied is False
    assert ledger.orders[order.order_id].filled_quantity == 4
    journal.close()
