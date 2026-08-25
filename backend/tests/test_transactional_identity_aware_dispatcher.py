from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_identity_gateway import ExecutionIdentityGateway
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_identity_aware_dispatcher import TransactionalIdentityAwareDispatcher


def test_live_dispatch_uses_transactional_identity(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5)
    identity = ExecutionIdentityGateway(repo)
    identity.bind(order_id, "upstox", "b1")
    dispatcher = TransactionalIdentityAwareDispatcher(CanonicalExecutionDispatcher(repo), identity)
    event = CanonicalExecutionEvent("e1", "b1", "wrong-client", "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox")
    result = dispatcher.dispatch(event)
    assert result.client_order_id == order_id
    assert result.dispatch.applied is True
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    repo.close()
