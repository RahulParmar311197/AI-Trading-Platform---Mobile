from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.execution_observability import ExecutionObservability


class ExecutionHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ExecutionHealthSnapshot:
    submissions: int
    submitted: int
    broker_failures: int
    recovery_found: int
    recovery_safe_retries: int
    quarantined: int
    duplicate_preventions: int
    broker_average_latency_ms: float
    recovery_average_latency_ms: float
    broker_healthy: bool
    recovery_healthy: bool
    quarantine_rate: float
    status: ExecutionHealthStatus


class ExecutionHealth:
    """Derives dashboard-safe execution severity from telemetry."""

    def __init__(self, observability: ExecutionObservability) -> None:
        self.observability = observability

    def snapshot(self) -> ExecutionHealthSnapshot:
        metrics = self.observability.snapshot()
        broker_avg = ExecutionObservability.average_latency_ms(metrics.broker_latency_ms_total, metrics.broker_latency_samples)
        recovery_avg = ExecutionObservability.average_latency_ms(metrics.recovery_latency_ms_total, metrics.recovery_latency_samples)
        quarantine_rate = metrics.quarantined / metrics.submissions if metrics.submissions else 0.0
        broker_healthy = metrics.broker_failures == 0 and broker_avg < 5000
        recovery_healthy = recovery_avg < 5000 and quarantine_rate < 0.05
        if metrics.broker_failures > 0 or broker_avg >= 10000 or quarantine_rate >= 0.20:
            status = ExecutionHealthStatus.CRITICAL
        elif broker_avg >= 5000 or recovery_avg >= 5000 or quarantine_rate >= 0.05 or not broker_healthy or not recovery_healthy:
            status = ExecutionHealthStatus.DEGRADED
        else:
            status = ExecutionHealthStatus.HEALTHY
        return ExecutionHealthSnapshot(
            metrics.submissions, metrics.submitted, metrics.broker_failures,
            metrics.recovery_found, metrics.recovery_safe_retries,
            metrics.quarantined, metrics.duplicate_preventions,
            broker_avg, recovery_avg, broker_healthy, recovery_healthy,
            quarantine_rate, status,
        )
