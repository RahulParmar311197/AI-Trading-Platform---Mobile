from app.submission_recovery_audit import SubmissionRecoveryAuditor
from app.submission_recovery_authorization import RecoveryApproval, RoleAndScopeRecoveryAuthorizer
from app.submission_recovery_runner import SubmissionRecoveryRunner


def test_audit_serialization_is_json():
    event = SubmissionRecoveryAuditor().record(
        event="BROKER_LOOKUP",
        idempotency_key="idem-1",
        client_order_id="client-1",
        status="FOUND",
        broker_order_id="broker-1",
    )
    payload = event.to_json()
    assert '"event": "BROKER_LOOKUP"' in payload
    assert '"idempotency_key": "idem-1"' in payload


def test_runner_contract_exposes_bounded_stats():
    class EmptyOrchestrator:
        def recover_pending(self, *, limit, approval):
            assert limit == 1
            assert approval.broker_account_id == 7
            return []

    approval = RecoveryApproval("operator-1", "recovery_operator", 7, "upstox:account:7")
    run = SubmissionRecoveryRunner(EmptyOrchestrator()).run_once(approval=approval, limit=1)
    assert run.results == []
    assert run.stats.scanned == 0
    assert run.stats.submitted == 0
    assert run.stats.quarantined == 0
    assert run.stats.duration_ms >= 0


def test_recovery_authorizer_fails_closed_for_unauthorized_role():
    authorizer = RoleAndScopeRecoveryAuthorizer()
    approval = RecoveryApproval("user-1", "trader", 7, "upstox:account:7")
    try:
        authorizer.authorize(approval)
    except PermissionError as exc:
        assert "not authorized" in str(exc)
    else:
        raise AssertionError("unauthorized recovery role must be rejected")


def test_recovery_authorizer_accepts_scoped_operator():
    authorizer = RoleAndScopeRecoveryAuthorizer()
    authorizer.authorize(RecoveryApproval("operator-1", "recovery_operator", 7, "upstox:account:7"))
