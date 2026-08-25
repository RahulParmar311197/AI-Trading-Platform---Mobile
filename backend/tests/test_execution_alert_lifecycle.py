import pytest

from app.execution_alert_store import ExecutionAlertStore


def test_alert_can_be_acknowledged_and_resolved(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    alert = store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")

    acknowledged = store.acknowledge(alert.alert_id)
    assert acknowledged.status == "ACKNOWLEDGED"
    assert acknowledged.acknowledged_at is not None

    resolved = store.resolve(alert.alert_id)
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at is not None


def test_cannot_acknowledge_resolved_alert(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    alert = store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")
    store.resolve(alert.alert_id)

    with pytest.raises(ValueError):
        store.acknowledge(alert.alert_id)
