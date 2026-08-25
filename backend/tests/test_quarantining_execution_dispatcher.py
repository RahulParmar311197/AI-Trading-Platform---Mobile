from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentityRegistry
from app.quarantining_execution_dispatcher import QuarantiningExecutionDispatcher
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_unknown_broker_order_is_quarantined(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    registry = OrderIdentityRegistry(db)
    quarantine = ExecutionEventQuarantine(db)
    dispatcher = QuarantiningExecutionDispatcher(CanonicalExecutionDispatcher(repo), registry, quarantine)
    event = CanonicalExecutionEvent("unknown-1", "missing-broker-order", order_id, "NIFTY", "BUY", CanonicalExecutionEventType.FILLED, 5, 1000, broker="upstox")
    result = dispatcher.dispatch(event)
    assert result.dispatched is False
    assert result.quarantined is True
    assert repo.snapshot().positions == {}
    assert len(quarantine.pending()) == 1
    assert quarantine.pending()[0]["reason"] == "UNKNOWN_BROKER_ORDER"
    duplicate = dispatcher.dispatch(event)
    assert duplicate.quarantined is False
    assert len(quarantine.pending()) == 1
    quarantine.close()
    registry.close()
    repo.close()
