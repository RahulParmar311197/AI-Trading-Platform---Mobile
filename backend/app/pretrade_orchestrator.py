from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import TradingDecision
from app.order_intent import OrderIntent
from app.risk_engine import RiskLimits
from app.risk_gateway import RiskGatewayResult, authorize
from app.setup_risk_engine import RiskValidatedSetup, SetupRiskEngine


@dataclass(frozen=True)
class PreTradeResult:
    setup: RiskValidatedSetup | None
    gateway: RiskGatewayResult | None
    approved: bool
    reason: str


class PreTradeOrchestrator:
    """Single pre-trade path: setup validation first, authoritative portfolio gate second."""

    def __init__(self, setup_engine: SetupRiskEngine | None = None):
        self.setup_engine = setup_engine or SetupRiskEngine()

    def authorize_decision(
        self,
        *,
        symbol: str,
        decision: TradingDecision,
        equity: float,
        daily_pnl: float,
        open_positions: int,
        recent_losses: int = 0,
        limits: RiskLimits | None = None,
        price_increment: float = 0.0,
    ) -> PreTradeResult:
        setup = self.setup_engine.validate(decision, equity, price_increment)
        if setup is None:
            return PreTradeResult(None, None, False, "decision is HOLD")
        if not setup.approved:
            return PreTradeResult(setup, None, False, setup.reason)

        order = OrderIntent(
            symbol=symbol,
            side=setup.side,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=setup.target,
            quantity=setup.quantity,
            risk_amount=setup.risk_amount,
            source="AI_DECISION",
            confidence=decision.confidence,
        )
        gateway = authorize(
            order=order,
            equity=equity,
            daily_pnl=daily_pnl,
            open_positions=open_positions,
            recent_losses=recent_losses,
            limits=limits,
        )
        reason = "pre-trade checks passed" if gateway.approved else "; ".join(gateway.decision.reasons)
        return PreTradeResult(setup, gateway, gateway.approved, reason)
