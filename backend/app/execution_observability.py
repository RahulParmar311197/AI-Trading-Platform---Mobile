from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ExecutionMetricsSnapshot:
    submissions: int
    submitted: int
    broker_failures: int
    recovery_found: int
    recovery_safe_retries: int
    quarantined: int
    duplicate_preventions: int


class ExecutionObservability:
    """Process-local counters for the execution boundary; expose snapshots to telemetry later."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {
            "submissions": 0,
            "submitted": 0,
            "broker_failures": 0,
            "recovery_found": 0,
            "recovery_safe_retries": 0,
            "quarantined": 0,
            "duplicate_preventions": 0,
        }

    def increment(self, metric: str, amount: int = 1) -> None:
        if metric not in self._values or amount < 0:
            raise ValueError("invalid execution metric")
        with self._lock:
            self._values[metric] += amount

    def snapshot(self) -> ExecutionMetricsSnapshot:
        with self._lock:
            return ExecutionMetricsSnapshot(**self._values)
