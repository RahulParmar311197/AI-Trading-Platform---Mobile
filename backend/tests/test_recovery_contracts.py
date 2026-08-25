from app.submission_recovery_audit import SubmissionRecoveryAuditor
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
        def recover_pending(self, *, limit):
            assert limit == 1
            return []

    run = SubmissionRecoveryRunner(EmptyOrchestrator()).run_once(limit=1)
    assert run.results == []
    assert run.stats.scanned == 0
    assert run.stats.submitted == 0
    assert run.stats.quarantined == 0
    assert run.stats.duration_ms >= 0
