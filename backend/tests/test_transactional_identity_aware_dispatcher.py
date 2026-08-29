from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_identity_gateway import ExecutionIdentityGateway
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository
from app.transactional_identity_aware_dispatcher import TransactionalIdentityAwareDispatcher


def test_live_dispatch_uses_transactional_identity(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=101, broker_route="UPSTOX")
    identity = ExecutionIdentityGateway(repo)
    identity.bind(
        OrderIdentity(
            client_order_id=order_id,
            broker="upstox",
            broker_order_id="b1",
            broker_account_id=101,
            broker_route="UPSTOX",
        )
    )
    dispatcher = TransactionalIdentityAwareDispatcher(CanonicalExecutionDispatcher(repo), identity)
    event = CanonicalExecutionEvent(
        "e1", "b1", "wrong-client", "NIFTY", "BUY",
        CanonicalExecutionEventType.FILLED, 5, 1000,
        broker="upstox", broker_account_id=101, broker_route="UPSTOX",
    )
    result = dispatcher.dispatch(event)
    assert result.client_order_id == order_id
    assert result.dispatch.applied is True
    assert repo.snapshot().positions == {(101, "UPSTOX", "NIFTY"): 5.0}
    repo.close()
