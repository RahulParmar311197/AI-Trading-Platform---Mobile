from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.execution_observability import ExecutionObservability


class ExecutionHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class ExecutionHealthReason(str, Enum):
    BROKER_FAILURE = "BROKER_FAILURE"
    BROKER_LATENCY_HIGH = "BROKER_LATENCY_HIGH"
    RECOVERY_LATENCY_HIGH = "RECOVERY_LATENCY_HIGH"
    QUARANTINE_RATE_HIGH = "QUARANTINE_RATE_HIGH"


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
    reason_codes: tuple[str, ...]


class ExecutionHealth:
    """Derives dashboard-safe execution severity and machine-readable reasons."""

    def __init__(self, observability: ExecutionObservability) -> None:
        self.observability = observability

    def snapshot(self) -> ExecutionHealthSnapshot:
        metrics = self.observability.snapshot()
        broker_avg = ExecutionObservability.average_latency_ms(metrics.broker_latency_ms_total, metrics.broker_latency_samples)
        recovery_avg = ExecutionObservability.average_latency_ms(metrics.recovery_latency_ms_total, metrics.recovery_latency_samples)
        quarantine_rate = metrics.quarantined / metrics.submissions if metrics.submissions else 0.0
        reasons: list[str] = []
        if metrics.broker_failures > 0:
            reasons.append(ExecutionHealthReason.BROKER_FAILURE.value)
        if broker_avg >= 5000:
            reasons.append(ExecutionHealthReason.BROKER_LATENCY_HIGH.value)
        if recovery_avg >= 5000:
            reasons.append(ExecutionHealthReason.RECOVERY_LATENCY_HIGH.value)
        if quarantine_rate >= 0.05:
            reasons.append(ExecutionHealthReason.QUARANTINE_RATE_HIGH.value)
        broker_healthy = metrics.broker_failures == 0 and broker_avg < 5000
        recovery_healthy = recovery_avg < 5000 and quarantine_rate < 0.05
        if metrics.broker_failures > 0 or broker_avg >= 10000 or quarantine_rate >= 0.20:
            status = ExecutionHealthStatus.CRITICAL
        elif reasons:
            status = ExecutionHealthStatus.DEGRADED
        else:
            status = ExecutionHealthStatus.HEALTHY
        return ExecutionHealthSnapshot(
            metrics.submissions, metrics.submitted, metrics.broker_failures,
            metrics.recovery_found, metrics.recovery_safe_retries,
            metrics.quarantined, metrics.duplicate_preventions,
            broker_avg, recovery_avg, broker_healthy, recovery_healthy,
            quarantine_rate, status, tuple(reasons),
        )
