from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.execution_identity_gateway import ExecutionIdentityGateway
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_quarantine_recovery import TransactionalQuarantineRecovery


def test_recovery_uses_same_identity_gateway(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    identity = ExecutionIdentityGateway(repo)
    identity.bind(order_id, "upstox", "b1")
    quarantine = ExecutionEventQuarantine(db)
    quarantine.quarantine(event_id="q1", broker="upstox", broker_order_id="b1", payload={"symbol":"NIFTY","side":"BUY","event_type":"FILLED","quantity":5,"price":1000}, reason="UNKNOWN_BROKER_ORDER")
    worker = TransactionalQuarantineRecovery(identity, quarantine, CanonicalExecutionDispatcher(repo))
    result = worker.recover()
    assert result.recovered == 1
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    assert quarantine.pending() == []
    quarantine.close(); repo.close()
