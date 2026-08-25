from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class CircuitBreakerConfig:
    max_daily_loss: float = 0.0
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    block_on_reconciliation_drift: bool = True
    block_on_stale_data: bool = True


@dataclass(frozen=True)
class CircuitBreakerStatus:
    blocked: bool
    reason: str = ""


class TradingRiskCircuitBreaker:
    """Fail-closed gate for severe account, data, and reconciliation conditions."""

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._blocked = False
        self._reason = ""
        self._lock = Lock()

    def evaluate(self, *, daily_pnl: float, drawdown: float, consecutive_losses: int,
                 reconciliation_drift: bool = False, stale_data: bool = False) -> CircuitBreakerStatus:
        reasons: list[str] = []
        if self.config.max_daily_loss > 0 and daily_pnl <= -abs(self.config.max_daily_loss):
            reasons.append("max_daily_loss")
        if self.config.max_drawdown > 0 and drawdown >= abs(self.config.max_drawdown):
            reasons.append("max_drawdown")
        if self.config.max_consecutive_losses > 0 and consecutive_losses >= self.config.max_consecutive_losses:
            reasons.append("max_consecutive_losses")
        if self.config.block_on_reconciliation_drift and reconciliation_drift:
            reasons.append("reconciliation_drift")
        if self.config.block_on_stale_data and stale_data:
            reasons.append("stale_data")
        with self._lock:
            if reasons:
                self._blocked = True
                self._reason = ",".join(reasons)
            return CircuitBreakerStatus(self._blocked, self._reason)

    def can_trade(self) -> bool:
        with self._lock:
            return not self._blocked

    def engage(self, reason: str) -> None:
        if not reason:
            raise ValueError("reason is required")
        with self._lock:
            self._blocked = True
            self._reason = reason

    def reset(self) -> None:
        with self._lock:
            self._blocked = False
            self._reason = ""

    def status(self) -> CircuitBreakerStatus:
        with self._lock:
            return CircuitBreakerStatus(self._blocked, self._reason)
