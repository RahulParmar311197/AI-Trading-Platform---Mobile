from __future__ import annotations
from dataclasses import dataclass

@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.10
    max_open_positions: int = 3
    max_position_risk_pct: float = 0.01
    max_gross_exposure_pct: float = 1.0
    max_single_position_pct: float = 0.25

@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    quantity: float
    risk_amount: float

def check_trade(*, equity: float, day_start_equity: float, peak_equity: float, open_positions: int, entry: float, stop: float, config: RiskConfig, existing_exposure: float = 0.0) -> RiskDecision:
    if equity <= 0 or day_start_equity <= 0 or peak_equity <= 0 or entry <= 0 or stop <= 0:
        return RiskDecision(False, "invalid account or price", 0.0, 0.0)
    daily_loss = max(0.0, (day_start_equity - equity) / day_start_equity)
    drawdown = max(0.0, (peak_equity - equity) / peak_equity)
    if daily_loss >= config.max_daily_loss_pct: return RiskDecision(False, "daily loss limit reached", 0.0, 0.0)
    if drawdown >= config.max_drawdown_pct: return RiskDecision(False, "maximum drawdown limit reached", 0.0, 0.0)
    if open_positions >= config.max_open_positions: return RiskDecision(False, "maximum open positions reached", 0.0, 0.0)
    distance = abs(entry - stop)
    if distance <= 0: return RiskDecision(False, "invalid stop distance", 0.0, 0.0)
    risk_amount = equity * config.max_position_risk_pct
    qty = min(risk_amount / distance, (equity * config.max_single_position_pct) / entry)
    if existing_exposure + qty * entry > equity * config.max_gross_exposure_pct:
        return RiskDecision(False, "gross exposure limit reached", 0.0, 0.0)
    return RiskDecision(qty > 0, "risk checks passed" if qty > 0 else "calculated quantity is zero", qty, qty * distance)
