"""Canonical bridge from ICT/technical confluence into existing AI execution."""
from __future__ import annotations

from dataclasses import dataclass

from app.ai_execution_orchestrator import AIExecutionOrchestrator, AIExecutionResult
from app.signal_confluence import SignalDecision, evaluate_confluence


@dataclass(frozen=True)
class ConfluenceExecutionResult:
    signal: SignalDecision
    execution: AIExecutionResult | None


class ConfluenceExecutionOrchestrator:
    """Keep confluence advisory; only actionable signals reach AI execution."""

    def __init__(self, *, ai_orchestrator: AIExecutionOrchestrator) -> None:
        self.ai_orchestrator = ai_orchestrator

    async def evaluate_and_execute(
        self,
        context,
        *,
        ict=None,
        technical=None,
        equity: float,
        client_order_id: str,
        prediction=None,
        ml_confidence: float = 0.0,
        owner_user_id: int | None = None,
        broker_account_id: int | None = None,
        broker_route: str | None = None,
        broker_route_generation: str | None = None,
    ) -> ConfluenceExecutionResult:
        signal = evaluate_confluence(ict=ict, technical=technical)
        if signal.action == "HOLD":
            return ConfluenceExecutionResult(signal=signal, execution=None)

        execution = await self.ai_orchestrator.evaluate_and_execute(
            context,
            equity=equity,
            client_order_id=client_order_id,
            prediction=prediction,
            ml_confidence=ml_confidence,
            owner_user_id=owner_user_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            broker_route_generation=broker_route_generation,
        )
        return ConfluenceExecutionResult(signal=signal, execution=execution)


__all__ = ["ConfluenceExecutionResult", "ConfluenceExecutionOrchestrator"]
