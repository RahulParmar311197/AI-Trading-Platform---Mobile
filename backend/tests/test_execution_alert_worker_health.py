from app.execution_alert_worker_health import ExecutionAlertWorkerHealth


def test_worker_health_records_heartbeat(tmp_path):
    health = ExecutionAlertWorkerHealth(str(tmp_path / "worker.db"))
    health.started()
    health.tick(3, 2, 1)
    snapshot = health.snapshot()
    assert snapshot.status == "RUNNING"
    assert snapshot.processed_total == 3
    assert snapshot.delivered_total == 2
    assert snapshot.failed_total == 1
    assert snapshot.last_tick_at is not None
