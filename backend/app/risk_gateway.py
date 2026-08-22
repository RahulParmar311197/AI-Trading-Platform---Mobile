from __future__ import annotations
from dataclasses import dataclass
from app.order_intent import OrderIntent
from app.risk_engine import RiskDecision, RiskLimits, evaluate

@dataclass(frozen=True)
class RiskGatewayResult:
    approved: bool
    order: OrderIntent
    decision: RiskDecision


def authorize(*, order: OrderIntent, equity: float, daily_pnl: float, open_positions: int, recent_losses: int = 0, limits: RiskLimits | None = None) -> RiskGatewayResult:
    """Final pre-submit authorization. The order must already contain validated sizing/risk."""
    order.validate()
    decision = evaluate(
        equity=equity,
        daily_pnl=daily_pnl,
        proposed_risk=order.risk_amount,
        proposed_exposure=order.quantity * order.entry,
        open_positions=open_positions,
        recent_losses=recent_losses,
        limits=limits,
    )
    return RiskGatewayResult(decision.allowed, order, decision)
