from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.session_baseline import SessionBaselineStore
from app.session_risk import SessionPolicy


@dataclass(frozen=True)
class SessionRiskResult:
    allowed: bool
    reason: str
    session_start_equity: float


class SessionRiskGate:
    """Authoritative session baseline + daily-loss gate for pre-trade execution."""

    def __init__(self, baseline_store: SessionBaselineStore, policy: SessionPolicy | None = None):
        self.baseline_store = baseline_store
        self.policy = policy or SessionPolicy()

    def evaluate(self, timestamp: datetime, current_equity: float, realized_daily_pnl: float) -> SessionRiskResult:
        if current_equity <= 0:
            return SessionRiskResult(False, "invalid current equity", 0.0)
        baseline = self.baseline_store.get_or_create(timestamp, current_equity)
        if self.policy.daily_loss_locked(baseline.equity, realized_daily_pnl):
            return SessionRiskResult(False, "daily loss lock active", baseline.equity)
        return SessionRiskResult(True, "allowed", baseline.equity)
