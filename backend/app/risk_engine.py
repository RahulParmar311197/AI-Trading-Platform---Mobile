from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: list[str]
    risk_amount: float
    exposure: float


@dataclass
class RiskLimits:
    max_risk_percent: float = 1.0
    max_daily_loss_percent: float = 3.0
    max_exposure_percent: float = 20.0
    max_positions: int = 5
    cooldown_after_loss: int = 0


def evaluate(*, equity: float, daily_pnl: float, proposed_risk: float, proposed_exposure: float,
             open_positions: int, recent_losses: int = 0, limits: RiskLimits | None = None,
             current_exposure: float = 0.0, unrealized_pnl: float = 0.0) -> RiskDecision:
    """Evaluate pre-trade risk using authoritative equity and portfolio metrics.

    ``proposed_exposure`` is the post-trade exposure. ``current_exposure`` and
    ``unrealized_pnl`` are accepted as observability inputs so callers can keep
    risk decisions tied to the current portfolio state. Daily P&L remains the
    authoritative loss-limit input; callers should aggregate realized and
    unrealized P&L according to their broker/account semantics before calling.
    """
    limits = limits or RiskLimits()
    reasons: list[str] = []
    if equity <= 0:
        return RiskDecision(False, ["invalid equity"], 0, 0)
    risk_pct = proposed_risk / equity * 100
    exposure_pct = abs(proposed_exposure) / equity * 100
    daily_loss_pct = max(0, -daily_pnl / equity * 100)
    if risk_pct > limits.max_risk_percent:
        reasons.append("trade risk exceeds limit")
    if daily_loss_pct >= limits.max_daily_loss_percent:
        reasons.append("daily loss limit reached")
    if exposure_pct > limits.max_exposure_percent:
        reasons.append("portfolio exposure exceeds limit")
    if open_positions >= limits.max_positions:
        reasons.append("maximum open positions reached")
    if recent_losses < limits.cooldown_after_loss:
        reasons.append("loss cooldown active")
    return RiskDecision(not reasons, reasons, proposed_risk, proposed_exposure)
