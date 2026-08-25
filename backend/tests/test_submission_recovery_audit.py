from app.submission_recovery_audit import SubmissionRecoveryAuditor


def test_audit_event_contains_recovery_identity_and_status():
    auditor = SubmissionRecoveryAuditor()
    event = auditor.record(event="BROKER_LOOKUP", idempotency_key="idem-1", client_order_id="client-1", status="FOUND", broker_order_id="broker-1")
    assert event.event == "BROKER_LOOKUP"
    assert event.idempotency_key == "idem-1"
    assert event.client_order_id == "client-1"
    assert event.status == "FOUND"
    assert event.broker_order_id == "broker-1"
    assert event.occurred_at


def test_audit_can_use_external_sink():
    received = []
    auditor = SubmissionRecoveryAuditor(received.append)
    auditor.record(event="QUARANTINE", idempotency_key="idem-2", client_order_id="client-2", status="QUARANTINED", reason="ambiguous")
    assert len(received) == 1
    assert received[0].reason == "ambiguous"
