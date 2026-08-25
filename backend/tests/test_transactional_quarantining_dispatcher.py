from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.execution_identity_gateway import ExecutionIdentityGateway
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_quarantining_dispatcher import TransactionalQuarantiningDispatcher


def test_unknown_event_is_quarantined_without_execution_mutation(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    repo.create_order("NIFTY", "BUY", 5)
    identity = ExecutionIdentityGateway(repo)
    quarantine = ExecutionEventQuarantine(db)
    dispatcher = TransactionalQuarantiningDispatcher(CanonicalExecutionDispatcher(repo), identity, quarantine)
    event = CanonicalExecutionEvent("q1", "missing", "client-1", "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox")
    result = dispatcher.dispatch(event)
    assert result.quarantined is True
    assert result.dispatched is False
    assert repo.snapshot().positions == {}
    assert len(quarantine.pending()) == 1
    quarantine.close(); repo.close()
