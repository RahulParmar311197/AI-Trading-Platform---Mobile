from app.execution_alert_store import ExecutionAlertStore


def test_alert_store_persists_and_reads_recent_alerts(tmp_path):
    store = ExecutionAlertStore(str(tmp_path / "alerts.db"))
    created = store.record("CRITICAL", ("BROKER_FAILURE",), "CRITICAL:BROKER_FAILURE")
    records = store.recent()
    assert records[0].alert_id == created.alert_id
    assert records[0].severity == "CRITICAL"
    assert records[0].reason_codes == ("BROKER_FAILURE",)
