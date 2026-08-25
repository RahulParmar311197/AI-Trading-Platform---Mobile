from app.execution_alert_store import ExecutionAlertStore
from app.app_factory import create_resources


def test_observability_event_triggers_persistent_alert(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.db"),
        safety_path=str(tmp_path / "safety.json"),
        audit_path=str(tmp_path / "audit.jsonl"),
        alert_path=str(tmp_path / "alerts.db"),
    )

    resources.execution_observability.increment("submissions")
    resources.execution_observability.increment("broker_failures")

    records = resources.execution_alert_store.recent()
    assert records
    assert records[0].severity == "CRITICAL"
    assert records[0].reason_codes == ("BROKER_FAILURE",)
