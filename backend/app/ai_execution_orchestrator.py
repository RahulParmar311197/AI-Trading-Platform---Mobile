from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ai_decision_engine import AIDecisionEngine, TradingDecision
from app.ai_trade_intent import AITradeIntentConfig, build_ai_order_request
from app.broker_adapter import BrokerOrderRequest
from app.instruments import InstrumentProvider
from app.risk_engine import RiskDecision, RiskLimits, evaluate as evaluate_risk
from app.signal_confluence import SignalDecision


class OrderSubmitter(Protocol):
    async def submit(self, request: BrokerOrderRequest): ...


@dataclass(frozen=True)
class AIRiskSnapshot:
    """Authoritative portfolio state required before an AI order may execute."""

    daily_pnl: float
    open_positions: int
    recent_losses: int = 0
    current_exposure: float = 0.0
    unrealized_pnl: float = 0.0
    limits: RiskLimits | None = None


@dataclass(frozen=True)
class AIExecutionResult:
    decision: TradingDecision
    order_request: BrokerOrderRequest | None
    execution: object | None
    risk_decision: RiskDecision | None = None


class AIExecutionOrchestrator:
    """Canonical boundary from an AI decision through mandatory risk veto to execution."""

    def __init__(
        self,
        *,
        decision_engine: AIDecisionEngine,
        instrument_provider: InstrumentProvider,
        order_submitter: OrderSubmitter,
        intent_config: AITradeIntentConfig | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.instrument_provider = instrument_provider
        self.order_submitter = order_submitter
        self.intent_config = intent_config or AITradeIntentConfig()

    async def evaluate_and_execute(
        self,
        context,
        *,
        equity: float,
        client_order_id: str,
        prediction=None,
        ml_confidence: float = 0.0,
        confluence: SignalDecision | None = None,
        owner_user_id: int | None = None,
        broker_account_id: int | None = None,
        broker_route: str | None = None,
        broker_route_generation: str | None = None,
        risk_snapshot: AIRiskSnapshot | None = None,
    ) -> AIExecutionResult:
        decision = self.decision_engine.decide(
            context,
            prediction=prediction,
            ml_confidence=ml_confidence,
            confluence=confluence,
        )
        request = build_ai_order_request(
            decision,
            equity=equity,
            client_order_id=client_order_id,
            instrument_provider=self.instrument_provider,
            config=self.intent_config,
            owner_user_id=owner_user_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            broker_route_generation=broker_route_generation,
        )
        if request is None:
            return AIExecutionResult(decision=decision, order_request=None, execution=None)
        if risk_snapshot is None:
            raise RuntimeError("authoritative risk snapshot is required before AI execution")

        instrument = self.instrument_provider.resolve(request.symbol)
        if instrument is None:
            raise RuntimeError(f"instrument metadata unavailable for {request.symbol}")
        multiplier = float(instrument.multiplier)
        proposed_risk = abs(float(request.price) - float(request.stop)) * float(request.quantity) * multiplier
        proposed_exposure = abs(float(request.price)) * float(request.quantity) * multiplier
        risk_decision = evaluate_risk(
            equity=equity,
            daily_pnl=risk_snapshot.daily_pnl,
            proposed_risk=proposed_risk,
            proposed_exposure=proposed_exposure,
            open_positions=risk_snapshot.open_positions,
            recent_losses=risk_snapshot.recent_losses,
            limits=risk_snapshot.limits,
            current_exposure=risk_snapshot.current_exposure,
            unrealized_pnl=risk_snapshot.unrealized_pnl,
        )
        if not risk_decision.allowed:
            return AIExecutionResult(
                decision=decision,
                order_request=request,
                execution=None,
                risk_decision=risk_decision,
            )

        execution = await self.order_submitter.submit(request)
        return AIExecutionResult(
            decision=decision,
            order_request=request,
            execution=execution,
            risk_decision=risk_decision,
        )
