from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import TradingDecision
from app.order_intent import OrderIntent
from app.operational_metrics import TradingMetricsCollector
from app.risk_engine import RiskLimits
from app.risk_gateway import RiskGatewayResult, authorize
from app.risk_circuit_breaker import TradingRiskCircuitBreaker
from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.setup_risk_engine import RiskValidatedSetup, SetupRiskEngine
from app.trading_observability import TradingAuditLogger


@dataclass(frozen=True)
class PreTradeResult:
    setup: RiskValidatedSetup | None
    gateway: RiskGatewayResult | None
    approved: bool
    reason: str


class PreTradeOrchestrator:
    """Single fail-closed pre-trade path with setup, portfolio, and observable circuit-breaker gates."""

    def __init__(self, setup_engine: SetupRiskEngine | None = None,
                 circuit_breaker: TradingRiskCircuitBreaker | ObservableRiskCircuitBreaker | None = None,
                 metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None):
        self.setup_engine = setup_engine or SetupRiskEngine()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()
        if isinstance(circuit_breaker, ObservableRiskCircuitBreaker):
            self.circuit_breaker = circuit_breaker
        else:
            self.circuit_breaker = ObservableRiskCircuitBreaker(
                breaker=circuit_breaker or TradingRiskCircuitBreaker(),
                metrics=self.metrics,
                audit=self.audit,
            )

    def authorize_decision(
        self, *, symbol: str, decision: TradingDecision, equity: float, daily_pnl: float,
        open_positions: int, recent_losses: int = 0, limits: RiskLimits | None = None,
        price_increment: float = 0.0, drawdown: float = 0.0,
        reconciliation_drift: bool = False, stale_data: bool = False,
    ) -> PreTradeResult:
        breaker = self.circuit_breaker.evaluate(
            daily_pnl=daily_pnl, drawdown=drawdown, consecutive_losses=recent_losses,
            reconciliation_drift=reconciliation_drift, stale_data=stale_data,
        )
        if breaker.blocked:
            self.audit.emit("PRETRADE_BLOCKED", symbol=symbol, severity="WARNING",
                            data={"reason": breaker.reason})
            return PreTradeResult(None, None, False, f"circuit breaker: {breaker.reason}")

        setup = self.setup_engine.validate(decision, equity, price_increment)
        if setup is None:
            return PreTradeResult(None, None, False, "decision is HOLD")
        if not setup.approved:
            self.audit.emit("RISK_REJECTED", symbol=symbol, severity="WARNING", data={"reason": setup.reason})
            return PreTradeResult(setup, None, False, setup.reason)

        order = OrderIntent(symbol=symbol, side=setup.side, entry=setup.entry,
                            stop_loss=setup.stop_loss, take_profit=setup.target,
                            quantity=setup.quantity, risk_amount=setup.risk_amount,
                            source="AI_DECISION", confidence=decision.confidence)
        gateway = authorize(order=order, equity=equity, daily_pnl=daily_pnl,
                            open_positions=open_positions, recent_losses=recent_losses, limits=limits)
        reason = "pre-trade checks passed" if gateway.approved else "; ".join(gateway.decision.reasons)
        if not gateway.approved:
            self.audit.emit("RISK_REJECTED", symbol=symbol, severity="WARNING", data={"reason": reason})
        else:
            self.audit.emit("RISK_APPROVED", symbol=symbol, data={"reason": reason})
        return PreTradeResult(setup, gateway, gateway.approved, reason)
