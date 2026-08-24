from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.broker_adapter import BrokerOrderRequest
from app.ensemble import EnsembleDecision
from app.order_execution_service import ExecutionResult, OrderExecutionService


@dataclass(frozen=True)
class DecisionExecutionResult:
    executed: bool
    result: ExecutionResult | None
    reason: str


def execute_decision(
    decision: EnsembleDecision,
    execution: OrderExecutionService,
    request_factory: Callable[[str], BrokerOrderRequest],
) -> DecisionExecutionResult:
    """Convert an approved ensemble action into an execution request.

    NO_TRADE is a hard stop: it cannot create a lifecycle record, reserve risk,
    or reach the broker. BUY/SELL requests still pass through OrderExecutionService,
    which owns idempotency, startup, risk, and broker safeguards.
    """
    action = decision.action.upper().strip()
    if action not in {"BUY", "SELL"}:
        return DecisionExecutionResult(False, None, "NO_TRADE")

    request = request_factory(action)
    if request.side.upper().strip() != action:
        return DecisionExecutionResult(False, None, "DECISION_SIDE_MISMATCH")

    result = execution.submit(request)
    return DecisionExecutionResult(True, result, "EXECUTION_SUBMITTED_TO_SAFETY_LAYER")
