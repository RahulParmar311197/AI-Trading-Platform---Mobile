from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_dispatches_partial_and_full_fill(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 10)
    dispatcher = CanonicalExecutionDispatcher(repo)
    dispatcher.dispatch(CanonicalExecutionEvent("s1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.SUBMITTED))
    partial = dispatcher.dispatch(CanonicalExecutionEvent("f1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.PARTIAL_FILL, 4, 1000))
    assert partial.applied is True
    duplicate = dispatcher.dispatch(CanonicalExecutionEvent("f1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.PARTIAL_FILL, 4, 1000))
    assert duplicate.applied is False
    full = dispatcher.dispatch(CanonicalExecutionEvent("f2", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 6, 1001))
    assert full.applied is True
    assert repo.snapshot().positions == {"NIFTY": 10.0}
    repo.close()
