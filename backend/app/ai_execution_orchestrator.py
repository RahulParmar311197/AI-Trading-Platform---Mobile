from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ai_decision_engine import AIDecisionEngine, TradingDecision
from app.ai_trade_intent import AITradeIntentConfig, build_ai_order_request
from app.broker_adapter import BrokerOrderRequest
from app.broker_execution_context import BrokerExecutionContext
from app.broker_order_lifecycle import OrderStatus
from app.instruments import InstrumentProvider
from app.live_execution_gateway import ExecutionAuthorization, TrackedExecution
from app.risk_engine import RiskDecision, RiskLimits, evaluate as evaluate_risk
from app.signal_confluence import SignalDecision


class AuthorizedOrderSubmitter(Protocol):
    def authorize_request(self, request: BrokerOrderRequest, context: BrokerExecutionContext) -> ExecutionAuthorization: ...
    def execute_request(self, request: BrokerOrderRequest, authorization: ExecutionAuthorization, context: BrokerExecutionContext) -> TrackedExecution: ...


class RiskReservationProvider(Protocol):
    def reserve(
        self,
        *,
        reservation_id: str | None,
        client_order_id: str,
        broker_account_id: str,
        broker_route: str,
        amount: float,
        current_exposure: float,
        max_total_exposure: float,
    ) -> str: ...
    def release(self, reservation_id: str) -> None: ...


@dataclass(frozen=True)
class AIRiskSnapshot:
    """Authoritative portfolio state required before an AI order may execute."""
    daily_pnl: float
    open_positions: int
    recent_losses: int = 0
    current_exposure: float = 0.0
    unrealized_pnl: float = 0.0
    limits: RiskLimits | None = None
    snapshot_fingerprint: str | None = None


@dataclass(frozen=True)
class AIExecutionResult:
    decision: TradingDecision
    order_request: BrokerOrderRequest | None
    execution: object | None
    risk_decision: RiskDecision | None = None
    risk_reservation_id: str | None = None


class AIExecutionOrchestrator:
    """Canonical boundary from an AI decision through risk and live execution authorization."""
    def __init__(self, *, decision_engine: AIDecisionEngine, instrument_provider: InstrumentProvider, order_submitter: AuthorizedOrderSubmitter, intent_config: AITradeIntentConfig | None = None, risk_reservation_store: RiskReservationProvider | None = None) -> None:
        self.decision_engine = decision_engine
        self.instrument_provider = instrument_provider
        self.order_submitter = order_submitter
        self.intent_config = intent_config or AITradeIntentConfig()
        self.risk_reservation_store = risk_reservation_store

    async def evaluate_and_execute(self, context, *, equity: float, client_order_id: str, prediction=None, ml_confidence: float = 0.0, confluence: SignalDecision | None = None, owner_user_id: int | None = None, broker_account_id: str | None = None, broker_route: str | None = None, broker_route_generation: str | None = None, risk_snapshot: AIRiskSnapshot | None = None, broker_execution_context: BrokerExecutionContext | None = None) -> AIExecutionResult:
        decision = self.decision_engine.decide(context, prediction=prediction, ml_confidence=ml_confidence, confluence=confluence)
        request = build_ai_order_request(decision, equity=equity, client_order_id=client_order_id, instrument_provider=self.instrument_provider, config=self.intent_config, owner_user_id=owner_user_id, broker_account_id=broker_account_id, broker_route=broker_route, broker_route_generation=broker_route_generation)
        if request is None:
            return AIExecutionResult(decision=decision, order_request=None, execution=None)
        if risk_snapshot is None:
            raise RuntimeError("authoritative risk snapshot is required before AI execution")
        if broker_execution_context is None:
            raise RuntimeError("broker execution context is required before AI execution")
        self._validate_risk_snapshot_binding(risk_snapshot, broker_execution_context)
        instrument = self.instrument_provider.resolve(request.symbol)
        if instrument is None:
            raise RuntimeError(f"instrument metadata unavailable for {request.symbol}")
        multiplier = float(instrument.multiplier)
        proposed_risk = abs(float(request.price) - float(request.stop)) * float(request.quantity) * multiplier
        proposed_exposure = abs(float(request.price)) * float(request.quantity) * multiplier
        risk_decision = evaluate_risk(equity=equity, daily_pnl=risk_snapshot.daily_pnl, proposed_risk=proposed_risk, proposed_exposure=proposed_exposure, open_positions=risk_snapshot.open_positions, recent_losses=risk_snapshot.recent_losses, limits=risk_snapshot.limits, current_exposure=risk_snapshot.current_exposure, unrealized_pnl=risk_snapshot.unrealized_pnl)
        if not risk_decision.allowed:
            return AIExecutionResult(decision=decision, order_request=request, execution=None, risk_decision=risk_decision)
        if request.broker_account_id is not None and request.broker_account_id != broker_execution_context.account_id:
            raise RuntimeError("broker account identity does not match execution context")
        if request.broker_route is not None and request.broker_route != broker_execution_context.broker_route:
            raise RuntimeError("broker route does not match execution context")
        if request.broker_route_generation is not None and request.broker_route_generation != broker_execution_context.route_generation:
            raise RuntimeError("broker route generation does not match execution context")
        reservation_id = None
        if self.risk_reservation_store is not None:
            limits = risk_snapshot.limits or RiskLimits()
            account_id = broker_execution_context.account_id.strip()
            route = broker_execution_context.broker_route.strip()
            if not account_id or not route:
                raise RuntimeError("broker account and route are required for risk reservation")
            max_total_exposure = float(equity) * float(limits.max_exposure_percent) / 100.0
            try:
                reservation_id = self.risk_reservation_store.reserve(
                    reservation_id=None,
                    client_order_id=client_order_id,
                    broker_account_id=account_id,
                    broker_route=route,
                    amount=proposed_exposure,
                    current_exposure=risk_snapshot.current_exposure,
                    max_total_exposure=max_total_exposure,
                )
            except Exception as exc:
                raise RuntimeError("risk reservation could not be acquired; execution blocked") from exc
        authorize = getattr(self.order_submitter, "authorize_request", None)
        execute = getattr(self.order_submitter, "execute_request", None)
        if not callable(authorize) or not callable(execute):
            if reservation_id is not None:
                self.risk_reservation_store.release(reservation_id)
            raise RuntimeError("authorized execution gateway is required after AI risk approval")
        try:
            authorization = authorize(request, broker_execution_context)
        except Exception:
            if reservation_id is not None:
                self.risk_reservation_store.release(reservation_id)
            raise
        try:
            execution = execute(request, authorization, broker_execution_context)
        except Exception:
            # Keep the reservation on ambiguous broker outcomes so another
            # worker cannot reuse the same exposure before reconciliation.
            raise
        lifecycle = getattr(execution, "lifecycle", None)
        if reservation_id is not None and lifecycle is not None and getattr(lifecycle, "status", None) in {OrderStatus.REJECTED, OrderStatus.CANCELLED}:
            self.risk_reservation_store.release(reservation_id)
            reservation_id = None
        return AIExecutionResult(decision=decision, order_request=request, execution=execution, risk_decision=risk_decision, risk_reservation_id=reservation_id)

    @staticmethod
    def _validate_risk_snapshot_binding(risk_snapshot: AIRiskSnapshot, broker_execution_context: BrokerExecutionContext) -> None:
        fingerprint = (risk_snapshot.snapshot_fingerprint or "").strip()
        if not fingerprint:
            raise RuntimeError("authoritative risk snapshot fingerprint is required before AI execution")
        if fingerprint != broker_execution_context.snapshot_fingerprint:
            raise RuntimeError("risk snapshot does not match broker execution context")
