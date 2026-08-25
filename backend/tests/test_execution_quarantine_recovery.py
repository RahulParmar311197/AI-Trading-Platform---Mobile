from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.execution_quarantine_recovery import ExecutionQuarantineRecovery
from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_recovery_dispatches_once_after_mapping_arrives(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    registry = OrderIdentityRegistry(db)
    quarantine = ExecutionEventQuarantine(db)
    quarantine.quarantine(event_id="q1", broker="upstox", broker_order_id="b1", payload={"symbol":"NIFTY","side":"BUY","event_type":"FILLED","quantity":5,"price":1000}, reason="UNKNOWN_BROKER_ORDER")
    registry.bind(OrderIdentity(order_id, "upstox", "b1"))
    worker = ExecutionQuarantineRecovery(registry, quarantine, CanonicalExecutionDispatcher(repo))
    result = worker.recover()
    assert result.recovered == 1
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    assert quarantine.pending() == []
    again = worker.recover()
    assert again.recovered == 0
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    quarantine.close(); registry.close(); repo.close()
