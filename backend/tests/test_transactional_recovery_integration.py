from datetime import datetime, timezone

import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.reconciliation_matcher import InternalOrderCandidate
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository
from app.transactional_recovery_service import TransactionalRecoveryService


def _setup(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    quarantine = ExecutionEventQuarantine(str(tmp_path / "quarantine.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    event_id = "recovery-fill"
    quarantine.quarantine(event_id=event_id, broker="upstox", broker_order_id="broker-1", payload={"broker_account_id": 1, "broker_route": "primary"}, reason="MANUAL_REVIEW")
    case = quarantine.list_recovery_cases()[0]
    return repo, quarantine, order, event_id, case["id"]


def test_recovery_commits_identity_execution_and_resolution(tmp_path):
    repo, quarantine, order, event_id, case_id = _setup(tmp_path)
    service = TransactionalRecoveryService(repo, quarantine)
    identity = OrderIdentity(order, "upstox", "broker-1", 1, "primary")
    assert service.approve_and_apply(quarantine_id=case_id, identity=identity, event_id=event_id, event_kind="FILLED", quantity=5, price=1000, approver="operator-1") is True
    assert repo.get_identity_by_broker("upstox", "broker-1", broker_account_id=1, broker_route="primary") == identity
    assert repo.snapshot().positions == {(1, "primary", "NIFTY"): 5.0}
    assert repo.pending_outbox()[0]["event_id"] == event_id
    assert quarantine.list_recovery_cases() == []
    quarantine.close(); repo.close()


def test_invalid_recovery_rolls_back_and_leaves_case_open(tmp_path):
    repo, quarantine, order, event_id, case_id = _setup(tmp_path)
    service = TransactionalRecoveryService(repo, quarantine)
    bad_identity = OrderIdentity(order, "upstox", "wrong-broker-id", 1, "primary")
    with pytest.raises(ValueError, match="identity mismatch"):
        service.approve_and_apply(quarantine_id=case_id, identity=bad_identity, event_id=event_id, event_kind="FILLED", quantity=5, price=1000, approver="operator-1")
    assert repo.get_identity_by_broker("upstox", "broker-1", broker_account_id=1, broker_route="primary") is None
    assert repo.snapshot().positions == {}
    assert repo.pending_outbox() == []
    assert len(quarantine.list_recovery_cases()) == 1
    quarantine.close(); repo.close()
