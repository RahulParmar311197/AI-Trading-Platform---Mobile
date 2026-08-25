from app.execution_health import ExecutionHealth
from app.execution_observability import ExecutionObservability


def test_health_snapshot_derives_latency_and_rates():
    metrics = ExecutionObservability()
    metrics.increment("submissions", 10)
    metrics.increment("submitted", 9)
    metrics.increment("broker_failures", 1)
    metrics.increment("quarantined", 1)
    metrics.observe_latency("broker_latency", 100)
    metrics.observe_latency("recovery_latency", 200)
    snapshot = ExecutionHealth(metrics).snapshot()
    assert snapshot.broker_average_latency_ms == 100
    assert snapshot.recovery_average_latency_ms == 200
    assert snapshot.quarantine_rate == 0.1
    assert snapshot.broker_healthy is False
    assert snapshot.recovery_healthy is False


def test_empty_metrics_are_healthy_by_default():
    snapshot = ExecutionHealth(ExecutionObservability()).snapshot()
    assert snapshot.quarantine_rate == 0
    assert snapshot.broker_average_latency_ms == 0
    assert snapshot.recovery_average_latency_ms == 0
    assert snapshot.broker_healthy is True
    assert snapshot.recovery_healthy is True
