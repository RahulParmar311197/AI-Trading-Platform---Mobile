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
    broker_latency_ms_total: float
    broker_latency_samples: int
    recovery_latency_ms_total: float
    recovery_latency_samples: int


class ExecutionObservability:
    """Thread-safe process-local execution counters and latency aggregates."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {
            "submissions": 0, "submitted": 0, "broker_failures": 0,
            "recovery_found": 0, "recovery_safe_retries": 0,
            "quarantined": 0, "duplicate_preventions": 0,
            "broker_latency_ms_total": 0.0, "broker_latency_samples": 0,
            "recovery_latency_ms_total": 0.0, "recovery_latency_samples": 0,
        }

    def increment(self, metric: str, amount: int = 1) -> None:
        if metric not in self._values or not isinstance(amount, int) or amount < 0:
            raise ValueError("invalid execution metric")
        with self._lock:
            self._values[metric] += amount

    def observe_latency(self, metric: str, milliseconds: float) -> None:
        if metric not in {"broker_latency", "recovery_latency"} or milliseconds < 0:
            raise ValueError("invalid latency metric")
        with self._lock:
            self._values[f"{metric}_ms_total"] += float(milliseconds)
            self._values[f"{metric}_samples"] += 1

    def snapshot(self) -> ExecutionMetricsSnapshot:
        with self._lock:
            return ExecutionMetricsSnapshot(**self._values)

    @staticmethod
    def average_latency_ms(total: float, samples: int) -> float:
        return total / samples if samples else 0.0
