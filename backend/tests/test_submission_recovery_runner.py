from app.submission_recovery_runner import SubmissionRecoveryRunner


class Orchestrator:
    def recover_pending(self, *, limit):
        return [
            type("R", (), {"status": "SUBMITTED"})(),
            type("R", (), {"status": "QUARANTINED"})(),
        ][:limit]


def test_runner_returns_structured_stats():
    run = SubmissionRecoveryRunner(Orchestrator()).run_once(limit=10)
    assert run.stats.scanned == 2
    assert run.stats.submitted == 1
    assert run.stats.quarantined == 1
    assert run.stats.duration_ms >= 0


def test_runner_rejects_unbounded_limit():
    try:
        SubmissionRecoveryRunner(Orchestrator()).run_once(limit=1001)
    except ValueError as exc:
        assert "between 1 and 1000" in str(exc)
    else:
        raise AssertionError("expected ValueError")
