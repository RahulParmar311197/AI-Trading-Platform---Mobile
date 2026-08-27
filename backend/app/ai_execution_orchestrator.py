from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ai_decision_engine import AIDecisionEngine, TradingDecision
from app.ai_trade_intent import AITradeIntentConfig, build_ai_order_request
from app.broker_adapter import BrokerOrderRequest
from app.instruments import InstrumentProvider


class OrderSubmitter(Protocol):
    async def submit(self, request: BrokerOrderRequest): ...


@dataclass(frozen=True)
class AIExecutionResult:
    decision: TradingDecision
    order_request: BrokerOrderRequest | None
    execution: object | None


class AIExecutionOrchestrator:
    """Canonical boundary from an approved AI decision to the existing executor."""

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
        owner_user_id: int | None = None,
        broker_account_id: int | None = None,
        broker_route: str | None = None,
        broker_route_generation: str | None = None,
    ) -> AIExecutionResult:
        decision = self.decision_engine.decide(
            context,
            prediction=prediction,
            ml_confidence=ml_confidence,
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
        execution = await self.order_submitter.submit(request)
        return AIExecutionResult(decision=decision, order_request=request, execution=execution)
