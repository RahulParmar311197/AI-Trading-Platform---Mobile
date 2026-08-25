from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_scope_mismatch_rolls_back_order_position_event_and_outbox(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    dispatcher = CanonicalExecutionDispatcher(repo)
    event = CanonicalExecutionEvent("scope-mismatch", "b1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox", broker_account_id=2, broker_route="primary")
    try:
        dispatcher.dispatch(event)
        assert False, "scope mismatch must be rejected"
    except ValueError as exc:
        assert "identity mismatch" in str(exc)
    snapshot = repo.snapshot()
    assert snapshot.positions == {}
    assert repo.pending_outbox() == []
    repo.close()
