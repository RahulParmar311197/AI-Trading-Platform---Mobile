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


@dataclass(frozen=True)
class ExecutionMetricsScope:
    broker_account_id: int
    broker_route: str


class ExecutionObservability:
    """Thread-safe aggregate and broker-account-scoped execution counters."""

    _METRIC_NAMES = frozenset({
        "submissions", "submitted", "broker_failures", "recovery_found",
        "recovery_safe_retries", "quarantined", "duplicate_preventions",
    })

    def __init__(self) -> None:
        self._lock = Lock()
        self._values = self._empty_values()
        self._scoped_values: dict[ExecutionMetricsScope, dict[str, float | int]] = {}

    @staticmethod
    def _empty_values() -> dict[str, float | int]:
        return {
            "submissions": 0, "submitted": 0, "broker_failures": 0,
            "recovery_found": 0, "recovery_safe_retries": 0,
            "quarantined": 0, "duplicate_preventions": 0,
            "broker_latency_ms_total": 0.0, "broker_latency_samples": 0,
            "recovery_latency_ms_total": 0.0, "recovery_latency_samples": 0,
        }

    @staticmethod
    def _scope(broker_account_id: int, broker_route: str) -> ExecutionMetricsScope:
        if not isinstance(broker_account_id, int) or broker_account_id <= 0:
            raise ValueError("invalid broker account id")
        if not isinstance(broker_route, str) or not broker_route.strip():
            raise ValueError("invalid broker route")
        return ExecutionMetricsScope(broker_account_id, broker_route)

    def _scoped(self, scope: ExecutionMetricsScope) -> dict[str, float | int]:
        return self._scoped_values.setdefault(scope, self._empty_values())

    def increment(self, metric: str, amount: int = 1) -> None:
        if metric not in self._METRIC_NAMES or not isinstance(amount, int) or amount < 0:
            raise ValueError("invalid execution metric")
        with self._lock:
            self._values[metric] += amount

    def increment_scoped(self, metric: str, broker_account_id: int, broker_route: str, amount: int = 1) -> None:
        if metric not in self._METRIC_NAMES or not isinstance(amount, int) or amount < 0:
            raise ValueError("invalid execution metric")
        scope = self._scope(broker_account_id, broker_route)
        with self._lock:
            self._scoped(scope)[metric] += amount

    def observe_latency(self, metric: str, milliseconds: float) -> None:
        if metric not in {"broker_latency", "recovery_latency"} or milliseconds < 0:
            raise ValueError("invalid latency metric")
        with self._lock:
            self._values[f"{metric}_ms_total"] += float(milliseconds)
            self._values[f"{metric}_samples"] += 1

    def observe_latency_scoped(self, metric: str, broker_account_id: int, broker_route: str, milliseconds: float) -> None:
        if metric not in {"broker_latency", "recovery_latency"} or milliseconds < 0:
            raise ValueError("invalid latency metric")
        scope = self._scope(broker_account_id, broker_route)
        with self._lock:
            values = self._scoped(scope)
            values[f"{metric}_ms_total"] += float(milliseconds)
            values[f"{metric}_samples"] += 1

    @staticmethod
    def _snapshot(values: dict[str, float | int]) -> ExecutionMetricsSnapshot:
        return ExecutionMetricsSnapshot(**values)

    def snapshot(self) -> ExecutionMetricsSnapshot:
        with self._lock:
            return self._snapshot(dict(self._values))

    def snapshot_scoped(self, broker_account_id: int, broker_route: str) -> ExecutionMetricsSnapshot:
        scope = self._scope(broker_account_id, broker_route)
        with self._lock:
            return self._snapshot(dict(self._scoped_values.get(scope, self._empty_values())))

    @staticmethod
    def average_latency_ms(total: float, samples: int) -> float:
        return total / samples if samples else 0.0
