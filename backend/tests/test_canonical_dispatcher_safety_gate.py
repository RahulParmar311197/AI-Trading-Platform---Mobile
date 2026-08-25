import pytest

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.transactional_execution_repository import TransactionalExecutionRepository


def make_event(order_id):
    return CanonicalExecutionEvent("safe-event", "broker-1", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox", broker_account_id=1, broker_route="primary")


def test_dispatch_blocks_when_reconciliation_not_ready(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    dispatcher = CanonicalExecutionDispatcher(repo)
    with pytest.raises(PermissionError, match="RECONCILIATION_NOT_READY"):
        dispatcher.dispatch(make_event(order), reconciliation_ready=False)
    assert repo.snapshot().positions == {}
    repo.close()


def test_dispatch_blocks_on_emergency_halt(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    dispatcher = CanonicalExecutionDispatcher(repo)
    with pytest.raises(PermissionError, match="EMERGENCY_HALT"):
        dispatcher.dispatch(make_event(order), emergency_halt=True)
    assert repo.snapshot().positions == {}
    repo.close()
