from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import TradingDecision
from app.order_intent import OrderIntent
from app.operational_metrics import TradingMetricsCollector
from app.portfolio_exposure_risk import ExposureLimits, PortfolioExposureRisk
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
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
    """Single fail-closed pre-trade path with setup, exposure, portfolio-loss and circuit-breaker gates."""

    def __init__(self, setup_engine: SetupRiskEngine | None = None,
                 circuit_breaker: TradingRiskCircuitBreaker | ObservableRiskCircuitBreaker | None = None,
                 metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None,
                 exposure_risk: PortfolioExposureRisk | None = None,
                 portfolio_loss_risk: PortfolioLossRisk | None = None):
        self.setup_engine = setup_engine or SetupRiskEngine()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()
        self.exposure_risk = exposure_risk or PortfolioExposureRisk(ExposureLimits())
        self.portfolio_loss_risk = portfolio_loss_risk or PortfolioLossRisk(PortfolioRiskLimits())
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
        positions: dict[str, float] | None = None, open_order_notional: float = 0.0,
        positions_available: bool = True, exposure_price: float | None = None,
        open_risk: float = 0.0, portfolio_risk_data_available: bool = True,
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

        exposure = self.exposure_risk.evaluate(
            symbol=symbol, side=setup.side, quantity=setup.quantity,
            price=exposure_price if exposure_price is not None else setup.entry,
            positions=positions or {}, open_order_notional=open_order_notional,
            positions_available=positions_available,
        )
        if not exposure.approved:
            self.audit.emit("EXPOSURE_REJECTED", symbol=symbol, severity="WARNING", data={"reason": exposure.reason})
            return PreTradeResult(setup, None, False, exposure.reason)

        portfolio = self.portfolio_loss_risk.evaluate(
            daily_pnl=daily_pnl,
            current_drawdown=drawdown,
            open_risk=open_risk,
            proposed_risk=float(setup.risk_amount),
            positions_available=portfolio_risk_data_available,
        )
        if not portfolio.approved:
            self.audit.emit("PORTFOLIO_RISK_REJECTED", symbol=symbol, severity="WARNING", data={"reason": portfolio.reason})
            return PreTradeResult(setup, None, False, portfolio.reason)

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
