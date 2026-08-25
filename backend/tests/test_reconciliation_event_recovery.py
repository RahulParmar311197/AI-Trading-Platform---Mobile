from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentityRegistry
from app.reconciliation_event_recovery import IdentityMatch, ReconciliationEventRecovery
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_reconciliation_bind_then_recover(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    registry = OrderIdentityRegistry(db)
    quarantine = ExecutionEventQuarantine(db)
    quarantine.quarantine(event_id="q1", broker="upstox", broker_order_id="b1", payload={"symbol":"NIFTY","side":"BUY","event_type":"FILLED","quantity":5,"price":1000}, reason="UNKNOWN_BROKER_ORDER")
    recovery = ReconciliationEventRecovery(registry, quarantine, repo)
    recovery.bind_reconciled_identity(IdentityMatch("upstox", "b1", order_id))
    result = recovery.recover()
    assert result.recovered == 1
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    assert quarantine.pending() == []
    quarantine.close(); registry.close(); repo.close()
