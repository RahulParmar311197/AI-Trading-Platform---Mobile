from app.execution_health import ExecutionHealth, ExecutionHealthStatus
from app.execution_observability import ExecutionObservability


def test_empty_execution_is_healthy():
    snapshot = ExecutionHealth(ExecutionObservability()).snapshot()
    assert snapshot.status is ExecutionHealthStatus.HEALTHY


def test_slow_broker_is_degraded():
    metrics = ExecutionObservability()
    metrics.observe_latency("broker_latency", 6000)
    snapshot = ExecutionHealth(metrics).snapshot()
    assert snapshot.status is ExecutionHealthStatus.DEGRADED


def test_broker_failure_is_critical():
    metrics = ExecutionObservability()
    metrics.increment("submissions")
    metrics.increment("broker_failures")
    snapshot = ExecutionHealth(metrics).snapshot()
    assert snapshot.status is ExecutionHealthStatus.CRITICAL


def test_high_quarantine_rate_is_critical():
    metrics = ExecutionObservability()
    metrics.increment("submissions", 5)
    metrics.increment("quarantined")
    snapshot = ExecutionHealth(metrics).snapshot()
    assert snapshot.status is ExecutionHealthStatus.CRITICAL
