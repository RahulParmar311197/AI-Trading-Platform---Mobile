from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class TradingMetrics:
    signals: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    partial_fills: int = 0
    reconciliation_failures: int = 0
    circuit_breaker_blocks: int = 0
    execution_latency_ms: list[float] = field(default_factory=list)
    realized_pnl: float = 0.0
    max_drawdown: float = 0.0


class TradingMetricsCollector:
    """Small dependency-free metrics collector for API/monitoring integration."""

    def __init__(self):
        self.metrics = TradingMetrics()
        self._lock = Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            if not hasattr(self.metrics, name):
                raise ValueError(f"unknown metric: {name}")
            setattr(self.metrics, name, getattr(self.metrics, name) + amount)

    def record_latency(self, milliseconds: float) -> None:
        if milliseconds < 0:
            raise ValueError("latency cannot be negative")
        with self._lock:
            self.metrics.execution_latency_ms.append(float(milliseconds))

    def record_pnl(self, pnl: float) -> None:
        with self._lock:
            self.metrics.realized_pnl += float(pnl)

    def snapshot(self) -> dict:
        with self._lock:
            latencies = list(self.metrics.execution_latency_ms)
            ordered = sorted(latencies)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else 0.0
            return {
                "signals": self.metrics.signals,
                "orders_submitted": self.metrics.orders_submitted,
                "orders_filled": self.metrics.orders_filled,
                "orders_rejected": self.metrics.orders_rejected,
                "partial_fills": self.metrics.partial_fills,
                "reconciliation_failures": self.metrics.reconciliation_failures,
                "circuit_breaker_blocks": self.metrics.circuit_breaker_blocks,
                "execution_latency_ms_p95": p95,
                "realized_pnl": self.metrics.realized_pnl,
                "max_drawdown": self.metrics.max_drawdown,
            }
