from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_dispatches_partial_and_full_fill_with_account_identity(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    dispatcher = CanonicalExecutionDispatcher(repo)
    dispatcher.dispatch(CanonicalExecutionEvent("s1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.SUBMITTED, broker_account_id=7, broker_route="upstox:account:7"))
    partial = dispatcher.dispatch(CanonicalExecutionEvent("f1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.PARTIAL_FILL, 4, 1000, broker_account_id=7, broker_route="upstox:account:7"))
    assert partial.applied is True
    duplicate = dispatcher.dispatch(CanonicalExecutionEvent("f1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.PARTIAL_FILL, 4, 1000, broker_account_id=7, broker_route="upstox:account:7"))
    assert duplicate.applied is False
    full = dispatcher.dispatch(CanonicalExecutionEvent("f2", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 6, 1001, broker_account_id=7, broker_route="upstox:account:7"))
    assert full.applied is True
    assert repo.snapshot().positions == {(7, "upstox:account:7", "NIFTY"): 10.0}
    repo.close()


def test_dispatch_rejects_missing_account_identity(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 1, broker_account_id=7, broker_route="upstox:account:7")
    dispatcher = CanonicalExecutionDispatcher(repo)
    try:
        dispatcher.dispatch(CanonicalExecutionEvent("s1", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.SUBMITTED))
    except ValueError as exc:
        assert "broker account identity" in str(exc)
    else:
        raise AssertionError("missing broker account identity should fail closed")
    repo.close()
