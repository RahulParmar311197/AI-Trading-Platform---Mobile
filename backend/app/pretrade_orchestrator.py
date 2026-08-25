from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import TradingDecision
from app.broker_portfolio_provider import BrokerPortfolioProvider
from app.broker_portfolio_snapshot import BrokerPortfolioSnapshot
from app.broker_snapshot_freshness import BrokerSnapshotFreshnessPolicy
from app.broker_snapshot_risk_adapter import BrokerSnapshotRiskAdapter
from app.internal_trading_state_provider import InternalTradingStateProvider
from app.order_intent import OrderIntent
from app.operational_metrics import TradingMetricsCollector
from app.portfolio_exposure_risk import ExposureLimits, PortfolioExposureRisk
from app.portfolio_loss_risk import PortfolioLossRisk, PortfolioRiskLimits
from app.portfolio_risk_aggregation import OpenOrderRiskInput, PositionRiskInput, PortfolioRiskAggregator
from app.risk_engine import RiskLimits
from app.risk_gateway import RiskGatewayResult, authorize
from app.risk_circuit_breaker import TradingRiskCircuitBreaker
from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.setup_risk_engine import RiskValidatedSetup, SetupRiskEngine
from app.trading_observability import TradingAuditLogger
from app.trading_state_reconciliation import ReconciliationState, TradingStateReconciliationGuard


@dataclass(frozen=True)
class PreTradeResult:
    setup: RiskValidatedSetup | None
    gateway: RiskGatewayResult | None
    approved: bool
    reason: str


class PreTradeOrchestrator:
    """Single fail-closed pre-trade path with broker freshness and automatic state reconciliation."""

    def __init__(self, setup_engine: SetupRiskEngine | None = None,
                 circuit_breaker: TradingRiskCircuitBreaker | ObservableRiskCircuitBreaker | None = None,
                 metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None,
                 exposure_risk: PortfolioExposureRisk | None = None,
                 portfolio_loss_risk: PortfolioLossRisk | None = None,
                 risk_aggregator: PortfolioRiskAggregator | None = None,
                 snapshot_adapter: BrokerSnapshotRiskAdapter | None = None,
                 broker_provider: BrokerPortfolioProvider | None = None,
                 snapshot_freshness: BrokerSnapshotFreshnessPolicy | None = None,
                 reconciliation_guard: TradingStateReconciliationGuard | None = None,
                 internal_state_provider: InternalTradingStateProvider | None = None):
        self.setup_engine = setup_engine or SetupRiskEngine()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()
        self.exposure_risk = exposure_risk or PortfolioExposureRisk(ExposureLimits())
        self.portfolio_loss_risk = portfolio_loss_risk or PortfolioLossRisk(PortfolioRiskLimits())
        self.risk_aggregator = risk_aggregator or PortfolioRiskAggregator()
        self.snapshot_adapter = snapshot_adapter or BrokerSnapshotRiskAdapter()
        self.broker_provider = broker_provider
        self.snapshot_freshness = snapshot_freshness or BrokerSnapshotFreshnessPolicy()
        self.reconciliation_guard = reconciliation_guard or TradingStateReconciliationGuard()
        self.internal_state_provider = internal_state_provider
        if isinstance(circuit_breaker, ObservableRiskCircuitBreaker):
            self.circuit_breaker = circuit_breaker
        else:
            self.circuit_breaker = ObservableRiskCircuitBreaker(
                breaker=circuit_breaker or TradingRiskCircuitBreaker(), metrics=self.metrics, audit=self.audit,
            )

    def authorize_decision(
        self, *, symbol: str, decision: TradingDecision, equity: float, daily_pnl: float,
        open_positions: int, recent_losses: int = 0, limits: RiskLimits | None = None,
        price_increment: float = 0.0, drawdown: float = 0.0,
        reconciliation_drift: bool = False, stale_data: bool = False,
        positions: dict[str, float] | None = None, open_order_notional: float = 0.0,
        positions_available: bool = True, exposure_price: float | None = None,
        open_risk: float | None = None, portfolio_risk_data_available: bool | None = None,
        position_risk_inputs: list[PositionRiskInput] | None = None,
        open_order_risk_inputs: list[OpenOrderRiskInput] | None = None,
        broker_snapshot: BrokerPortfolioSnapshot | None = None,
        fetch_broker_snapshot: bool = True,
        internal_positions: dict[str, float] | None = None,
        internal_open_order_ids: set[str] | frozenset[str] | None = None,
        fetch_internal_state: bool = True,
    ) -> PreTradeResult:
        breaker = self.circuit_breaker.evaluate(
            daily_pnl=daily_pnl, drawdown=drawdown, consecutive_losses=recent_losses,
            reconciliation_drift=reconciliation_drift, stale_data=stale_data,
        )
        if breaker.blocked:
            self.audit.emit("PRETRADE_BLOCKED", symbol=symbol, severity="WARNING", data={"reason": breaker.reason})
            return PreTradeResult(None, None, False, f"circuit breaker: {breaker.reason}")

        setup = self.setup_engine.validate(decision, equity, price_increment)
        if setup is None:
            return PreTradeResult(None, None, False, "decision is HOLD")
        if not setup.approved:
            self.audit.emit("RISK_REJECTED", symbol=symbol, severity="WARNING", data={"reason": setup.reason})
            return PreTradeResult(setup, None, False, setup.reason)

        if broker_snapshot is None and fetch_broker_snapshot and self.broker_provider is not None:
            try:
                broker_snapshot = self.broker_provider.get_portfolio_snapshot()
            except Exception as exc:
                self.audit.emit("BROKER_SNAPSHOT_FETCH_FAILED", symbol=symbol, severity="ERROR", data={"error": str(exc)})
                return PreTradeResult(setup, None, False, "broker portfolio snapshot unavailable")

        if self.internal_state_provider is not None and fetch_internal_state and internal_positions is None and internal_open_order_ids is None:
            try:
                internal_state = self.internal_state_provider.get_state()
                internal_positions = internal_state.positions
                internal_open_order_ids = internal_state.open_order_ids
            except Exception as exc:
                self.audit.emit("INTERNAL_STATE_FETCH_FAILED", symbol=symbol, severity="ERROR", data={"error": str(exc)})
                return PreTradeResult(setup, None, False, "internal trading state unavailable")

        exposure_positions = positions or {}
        exposure_positions_available = positions_available
        if broker_snapshot is not None:
            freshness = self.snapshot_freshness.evaluate(broker_snapshot)
            if not freshness.fresh:
                self.audit.emit("BROKER_SNAPSHOT_STALE", symbol=symbol, severity="WARNING", data={"reason": freshness.reason, "age_seconds": freshness.age_seconds})
                return PreTradeResult(setup, None, False, freshness.reason)
            adapted = self.snapshot_adapter.adapt(broker_snapshot)
            if not adapted.available:
                self.audit.emit("BROKER_SNAPSHOT_RISK_REJECTED", symbol=symbol, severity="WARNING", data={"reason": adapted.reason})
                return PreTradeResult(setup, None, False, adapted.reason)
            exposure_positions = {p.symbol.upper(): p.quantity for p in adapted.positions}
            exposure_positions_available = True
            position_risk_inputs = list(adapted.positions)
            open_order_risk_inputs = list(adapted.open_orders)
            open_risk = None
            portfolio_risk_data_available = None

            if self.internal_state_provider is not None or internal_positions is not None or internal_open_order_ids is not None:
                broker_order_ids = {o.order_id for o in broker_snapshot.open_orders}
                reconciliation = self.reconciliation_guard.evaluate(
                    ReconciliationState(
                        internal_positions=internal_positions or {},
                        broker_positions=exposure_positions,
                        internal_open_order_ids=frozenset(internal_open_order_ids or ()),
                        broker_open_order_ids=frozenset(broker_order_ids),
                    )
                )
                if not reconciliation.clean:
                    self.audit.emit(
                        "RECONCILIATION_DRIFT_BLOCKED", symbol=symbol, severity="ERROR",
                        data={"reason": reconciliation.reason,
                              "position_differences": list(reconciliation.position_differences),
                              "missing_internal_orders": list(reconciliation.missing_internal_orders),
                              "missing_broker_orders": list(reconciliation.missing_broker_orders)},
                    )
                    return PreTradeResult(setup, None, False, reconciliation.reason)

        exposure = self.exposure_risk.evaluate(
            symbol=symbol, side=setup.side, quantity=setup.quantity,
            price=exposure_price if exposure_price is not None else setup.entry,
            positions=exposure_positions, open_order_notional=open_order_notional,
            positions_available=exposure_positions_available,
        )
        if not exposure.approved:
            self.audit.emit("EXPOSURE_REJECTED", symbol=symbol, severity="WARNING", data={"reason": exposure.reason})
            return PreTradeResult(setup, None, False, exposure.reason)

        if open_risk is None or portfolio_risk_data_available is None:
            risk_snapshot = self.risk_aggregator.calculate(position_risk_inputs or [], open_order_risk_inputs or [])
            open_risk = risk_snapshot.total_open_risk
            portfolio_risk_data_available = risk_snapshot.risk_data_available
            if not risk_snapshot.risk_data_available:
                self.audit.emit("PORTFOLIO_RISK_DATA_UNAVAILABLE", symbol=symbol, severity="WARNING", data={"unresolved_symbols": list(risk_snapshot.unresolved_symbols)})

        portfolio = self.portfolio_loss_risk.evaluate(
            daily_pnl=daily_pnl, current_drawdown=drawdown,
            open_risk=float(open_risk), proposed_risk=float(setup.risk_amount),
            positions_available=bool(portfolio_risk_data_available),
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
