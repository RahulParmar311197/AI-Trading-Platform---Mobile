import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository
from app.transactional_recovery_service import TransactionalRecoveryService


def _setup(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    quarantine = ExecutionEventQuarantine(str(tmp_path / "quarantine.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    event_id = "recovery-crash"
    quarantine.quarantine(event_id=event_id, broker="upstox", broker_order_id="broker-1", payload={"broker_account_id": 1, "broker_route": "primary"}, reason="MANUAL_REVIEW")
    case_id = quarantine.list_recovery_cases()[0]["id"]
    service = TransactionalRecoveryService(repo, quarantine)
    identity = OrderIdentity(order, "upstox", "broker-1", 1, "primary")
    return repo, quarantine, service, identity, event_id, case_id


def test_failure_before_resolution_rolls_back_execution_and_binding(tmp_path, monkeypatch):
    repo, quarantine, service, identity, event_id, case_id = _setup(tmp_path)

    def fail_resolution(*_args, **_kwargs):
        raise RuntimeError("injected resolution failure")

    monkeypatch.setattr(quarantine._db, "execute", fail_resolution)
    with pytest.raises(RuntimeError, match="injected resolution failure"):
        service.approve_and_apply(quarantine_id=case_id, identity=identity, event_id=event_id, event_kind="FILLED", quantity=5, price=1000, approver="operator")
    assert repo.get_identity_by_broker("upstox", "broker-1", broker_account_id=1, broker_route="primary") is None
    assert repo.snapshot().positions == {}
    assert repo.pending_outbox() == []
    quarantine.close(); repo.close()


def test_case_cannot_be_resolved_twice(tmp_path):
    repo, quarantine, service, identity, event_id, case_id = _setup(tmp_path)
    assert service.approve_and_apply(quarantine_id=case_id, identity=identity, event_id=event_id, event_kind="FILLED", quantity=5, price=1000, approver="operator") is True
    with pytest.raises(ValueError, match="no longer open"):
        service.approve_and_apply(quarantine_id=case_id, identity=identity, event_id=event_id, event_kind="FILLED", quantity=5, price=1000, approver="operator")
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 5.0}
    quarantine.close(); repo.close()
