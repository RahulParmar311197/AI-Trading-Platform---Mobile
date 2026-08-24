from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.ai_decision_engine import TradingDecision

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class RiskConfig:
    min_reward_risk: float = 2.0
    risk_fraction: float = 0.01
    max_position_notional_fraction: float = 1.0


@dataclass(frozen=True)
class RiskValidatedSetup:
    side: Side
    entry: float
    stop_loss: float
    target: float
    risk_per_unit: float
    reward_per_unit: float
    reward_risk: float
    risk_amount: float
    quantity: float
    notional: float
    approved: bool
    reason: str


class SetupRiskEngine:
    """Validates AI-proposed levels and calculates a bounded position size."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        if self.config.min_reward_risk <= 0 or not 0 < self.config.risk_fraction <= 1:
            raise ValueError("invalid risk configuration")
        if self.config.max_position_notional_fraction <= 0:
            raise ValueError("max notional fraction must be positive")

    def validate(self, decision: TradingDecision, equity: float, price_increment: float = 0.0) -> RiskValidatedSetup | None:
        if decision.decision not in {"BUY", "SELL"}:
            return None
        if equity <= 0:
            raise ValueError("equity must be positive")
        if decision.entry is None or decision.stop_loss is None or decision.target is None:
            return RiskValidatedSetup(decision.decision, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, "missing entry/stop/target")

        entry, stop, target = decision.entry, decision.stop_loss, decision.target
        if price_increment > 0:
            entry = round(entry / price_increment) * price_increment
            stop = round(stop / price_increment) * price_increment
            target = round(target / price_increment) * price_increment

        if decision.decision == "BUY":
            risk_per_unit = entry - stop
            reward_per_unit = target - entry
        else:
            risk_per_unit = stop - entry
            reward_per_unit = entry - target

        if risk_per_unit <= 0 or reward_per_unit <= 0:
            return RiskValidatedSetup(decision.decision, entry, stop, target, risk_per_unit, reward_per_unit, 0, 0, 0, 0, False, "invalid directional levels")

        rr = reward_per_unit / risk_per_unit
        risk_amount = equity * self.config.risk_fraction
        quantity = risk_amount / risk_per_unit
        max_notional = equity * self.config.max_position_notional_fraction
        quantity = min(quantity, max_notional / entry)
        notional = quantity * entry
        approved = rr >= self.config.min_reward_risk and quantity > 0
        reason = "risk/reward and sizing checks passed" if approved else "minimum reward/risk threshold not met"
        return RiskValidatedSetup(decision.decision, entry, stop, target, risk_per_unit, reward_per_unit, rr, risk_amount, quantity, notional, approved, reason)
