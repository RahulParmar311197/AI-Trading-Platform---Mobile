from app.execution_lifecycle import OrderStatus
from app.persistent_execution_ledger import PersistentExecutionLedger


def test_order_fill_and_position_survive_restart(tmp_path):
    path = str(tmp_path / "ledger.db")
    ledger = PersistentExecutionLedger(path)
    order_id = ledger.create(symbol="NIFTY", side="BUY", quantity=10)
    ledger.transition(order_id, OrderStatus.SUBMITTED)
    ledger.fill(order_id, 4)
    assert ledger.snapshot() == ({"NIFTY": 4.0}, frozenset({order_id}))
    ledger.close()

    reopened = PersistentExecutionLedger(path)
    assert reopened.snapshot() == ({"NIFTY": 4.0}, frozenset({order_id}))
    reopened.fill(order_id, 6)
    assert reopened.snapshot() == ({"NIFTY": 10.0}, frozenset())
    reopened.close()
