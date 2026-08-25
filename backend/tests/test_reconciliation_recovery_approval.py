import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.reconciliation_recovery_control import RecoveryCase, RecoveryClass, ReconciliationRecoveryControl
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_only_manual_review_can_be_approved(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    quarantine = ExecutionEventQuarantine(str(tmp_path / "execution.db"))
    control = ReconciliationRecoveryControl(repo, quarantine)
    case = RecoveryCase("c1", "upstox", "b1", 1, "primary", RecoveryClass.AMBIGUOUS_MATCH, {"quarantine_id": 1})
    with pytest.raises(ValueError, match="manually reviewed"):
        control.approve_bind(case, order_id="o1", approver="operator")
    quarantine.close(); repo.close()


def test_manual_approval_binds_exact_scope_and_resolves_case(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    quarantine = ExecutionEventQuarantine(db)
    qid = quarantine.quarantine(event_id="e1", broker="upstox", broker_order_id="b1", payload={}, reason="MANUAL_REVIEW")
    case = RecoveryCase("c1", "upstox", "b1", 1, "primary", RecoveryClass.MANUAL_REVIEW, {"quarantine_id": 1})
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    ReconciliationRecoveryControl(repo, quarantine).approve_bind(case, order_id=order, approver="operator")
    assert repo.get_identity_by_broker("upstox", "b1", broker_account_id=1, broker_route="primary") is not None
    assert quarantine.pending() == []
    quarantine.close(); repo.close()
