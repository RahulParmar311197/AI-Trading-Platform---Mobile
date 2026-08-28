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
    """Send only BUY/SELL decisions to the canonical safety/execution layer.

    ``executed`` means the order actually reached the broker submission path;
    a rejected/blocked execution is therefore reported as ``False``.
    """
    action = decision.action.upper().strip()
    if action not in {"BUY", "SELL"}:
        return DecisionExecutionResult(False, None, "NO_TRADE")

    request = request_factory(action)
    if request.side.upper().strip() != action:
        return DecisionExecutionResult(False, None, "DECISION_SIDE_MISMATCH")

    result = execution.submit(request)
    accepted_statuses = {"SUBMITTED", "PARTIALLY_FILLED", "FILLED"}
    executed = str(result.status).upper() in accepted_statuses
    reason = "EXECUTION_ACCEPTED" if executed else (result.message or "EXECUTION_REJECTED")
    return DecisionExecutionResult(executed, result, reason)
