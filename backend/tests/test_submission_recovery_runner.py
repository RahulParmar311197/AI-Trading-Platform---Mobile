from app.submission_recovery_authorization import RecoveryApproval
from app.submission_recovery_runner import SubmissionRecoveryRunner


class Orchestrator:
    def recover_pending(self, *, limit, approval):
        assert approval.operator_id == "ops-1"
        assert approval.role == "recovery_operator"
        assert approval.broker_account_id == 101
        assert approval.broker_route == "UPSTOX"
        return [
            type("R", (), {"status": "SUBMITTED"})(),
            type("R", (), {"status": "QUARANTINED"})(),
        ][:limit]


def approval():
    return RecoveryApproval(
        operator_id="ops-1",
        role="recovery_operator",
        broker_account_id=101,
        broker_route="UPSTOX",
    )


def test_runner_returns_structured_stats():
    run = SubmissionRecoveryRunner(Orchestrator()).run_once(approval=approval(), limit=10)
    assert run.stats.scanned == 2
    assert run.stats.submitted == 1
    assert run.stats.quarantined == 1
    assert run.stats.duration_ms >= 0


def test_runner_rejects_unbounded_limit():
    try:
        SubmissionRecoveryRunner(Orchestrator()).run_once(approval=approval(), limit=1001)
    except ValueError as exc:
        assert "between 1 and 1000" in str(exc)
    else:
        raise AssertionError("expected ValueError")
