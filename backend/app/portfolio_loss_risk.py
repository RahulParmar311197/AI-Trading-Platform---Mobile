from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRiskLimits:
    max_daily_loss: float = 0.0
    max_drawdown: float = 0.0
    max_risk_budget: float = 0.0


@dataclass(frozen=True)
class PortfolioRiskDecision:
    approved: bool
    reason: str
    projected_daily_pnl: float
    projected_drawdown: float
    projected_risk: float


class PortfolioLossRisk:
    """Fail-closed portfolio-level loss, drawdown and risk-budget gate."""

    def __init__(self, limits: PortfolioRiskLimits):
        self.limits = limits

    def evaluate(
        self,
        *,
        daily_pnl: float,
        current_drawdown: float,
        open_risk: float,
        proposed_risk: float,
        positions_available: bool = True,
    ) -> PortfolioRiskDecision:
        if not positions_available:
            return PortfolioRiskDecision(False, "portfolio risk data unavailable", daily_pnl, current_drawdown, open_risk + proposed_risk)
        if proposed_risk < 0 or open_risk < 0:
            return PortfolioRiskDecision(False, "invalid portfolio risk inputs", daily_pnl, current_drawdown, open_risk + proposed_risk)

        projected_risk = open_risk + proposed_risk
        if self.limits.max_daily_loss > 0 and daily_pnl - proposed_risk < -self.limits.max_daily_loss:
            return PortfolioRiskDecision(False, "projected daily loss limit exceeded", daily_pnl - proposed_risk, current_drawdown, projected_risk)
        if self.limits.max_drawdown > 0 and current_drawdown + proposed_risk > self.limits.max_drawdown:
            return PortfolioRiskDecision(False, "projected drawdown limit exceeded", daily_pnl, current_drawdown + proposed_risk, projected_risk)
        if self.limits.max_risk_budget > 0 and projected_risk > self.limits.max_risk_budget:
            return PortfolioRiskDecision(False, "portfolio risk budget exceeded", daily_pnl, current_drawdown, projected_risk)
        return PortfolioRiskDecision(True, "within portfolio risk limits", daily_pnl, current_drawdown, projected_risk)
