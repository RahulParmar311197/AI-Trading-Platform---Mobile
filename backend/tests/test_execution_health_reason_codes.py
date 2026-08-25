from app.execution_health import ExecutionHealth, ExecutionHealthReason, ExecutionHealthStatus
from app.execution_health_dto import ExecutionHealthDTO
from app.execution_observability import ExecutionObservability


def test_multiple_degradation_reasons_are_reported():
    metrics = ExecutionObservability()
    metrics.increment("submissions", 10)
    metrics.increment("quarantined")
    metrics.observe_latency("broker_latency", 6000)
    metrics.observe_latency("recovery_latency", 7000)

    snapshot = ExecutionHealth(metrics).snapshot()

    assert snapshot.status is ExecutionHealthStatus.DEGRADED
    assert snapshot.reason_codes == (
        ExecutionHealthReason.BROKER_LATENCY_HIGH.value,
        ExecutionHealthReason.RECOVERY_LATENCY_HIGH.value,
        ExecutionHealthReason.QUARANTINE_RATE_HIGH.value,
    )


def test_critical_failure_keeps_all_relevant_reasons():
    metrics = ExecutionObservability()
    metrics.increment("submissions")
    metrics.increment("broker_failures")
    metrics.observe_latency("broker_latency", 10000)

    snapshot = ExecutionHealth(metrics).snapshot()
    payload = ExecutionHealthDTO.from_snapshot(snapshot)

    assert snapshot.status is ExecutionHealthStatus.CRITICAL
    assert ExecutionHealthReason.BROKER_FAILURE.value in payload["reason_codes"]
    assert ExecutionHealthReason.BROKER_LATENCY_HIGH.value in payload["reason_codes"]
    assert payload["status"] == "CRITICAL"
    assert isinstance(payload["reason_codes"], list)
