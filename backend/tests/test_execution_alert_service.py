from app.execution_alert_policy import ExecutionAlertPolicy
from app.execution_alert_service import ExecutionAlertService
from app.execution_alert_store import ExecutionAlertStore
from app.execution_health import ExecutionHealth
from app.execution_observability import ExecutionObservability


def test_service_persists_policy_approved_alert(tmp_path):
    observability = ExecutionObservability()
    observability.increment("submissions")
    observability.increment("broker_failures")
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    service = ExecutionAlertService(ExecutionHealth(observability), ExecutionAlertPolicy(), store)

    alert = service.evaluate(now=1000)

    assert alert is not None
    assert alert.severity == "CRITICAL"
    assert alert.reason_codes == ("BROKER_FAILURE",)
    assert store.recent()[0].alert_id == alert.alert_id
