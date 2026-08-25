from app.execution_alert_resolution import ExecutionAlertResolutionService
from app.execution_alert_store import ExecutionAlertStore
from app.execution_health import ExecutionHealth
from app.execution_observability import ExecutionObservability


def test_open_and_acknowledged_alerts_resolve_when_health_recovers(tmp_path):
    observability = ExecutionObservability()
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    open_alert = store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")
    acknowledged = store.record("DEGRADED", ("BROKER_LATENCY_HIGH",), "DEGRADED:BROKER_LATENCY_HIGH")
    store.acknowledge(acknowledged.alert_id)

    resolved = ExecutionAlertResolutionService(ExecutionHealth(observability), store).evaluate()

    assert {r.alert_id for r in resolved} == {open_alert.alert_id, acknowledged.alert_id}
    assert all(r.status == "RESOLVED" for r in resolved)


def test_unhealthy_state_does_not_auto_resolve(tmp_path):
    observability = ExecutionObservability()
    observability.increment("broker_failures")
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    alert = store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")

    resolved = ExecutionAlertResolutionService(ExecutionHealth(observability), store).evaluate()

    assert resolved == []
    assert store.recent()[0].status == "OPEN"
