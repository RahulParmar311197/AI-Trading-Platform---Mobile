from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.identity_aware_execution_dispatcher import IdentityAwareExecutionDispatcher
from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_broker_order_resolves_to_internal_order(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    registry = OrderIdentityRegistry(db)
    registry.bind(OrderIdentity(order_id, "upstox", "broker-1"))
    dispatcher = IdentityAwareExecutionDispatcher(CanonicalExecutionDispatcher(repo), registry)
    event = CanonicalExecutionEvent("fill-1", "broker-1", "wrong-client", "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox")
    result = dispatcher.dispatch(event)
    assert result.client_order_id == order_id
    assert result.dispatch.applied is True
    assert repo.snapshot().positions == {"NIFTY": 5.0}
    registry.close()
    repo.close()
