from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_safety_gate import ExecutionAuthorization, ExecutionSafetyContext, ExecutionSafetyGate
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class DispatchResult:
    applied: bool
    event_id: str
    event_type: CanonicalExecutionEventType


class CanonicalExecutionDispatcher:
    """Translate canonical broker events through the single safety + execution boundary."""

    def __init__(self, repository: TransactionalExecutionRepository, safety_gate: ExecutionSafetyGate | None = None) -> None:
        self.repository = repository
        self.safety_gate = safety_gate or ExecutionSafetyGate()

    def dispatch(self, event: CanonicalExecutionEvent, *, reconciliation_ready: bool = True, broker_healthy: bool = True, risk_allowed: bool = True, emergency_halt: bool = False) -> DispatchResult:
        if event.broker_account_id is None or not event.broker_route:
            raise ValueError("broker account identity is required for execution dispatch")
        authorization: ExecutionAuthorization = self.safety_gate.authorize(ExecutionSafetyContext(
            emergency_halt=emergency_halt,
            reconciliation_ready=reconciliation_ready,
            broker_healthy=broker_healthy,
            risk_allowed=risk_allowed,
            broker_account_id=event.broker_account_id,
            broker_route=event.broker_route,
        ))
        if not authorization.allowed:
            raise PermissionError(f"execution blocked: {authorization.reason.value}")
        kwargs = {"broker_account_id": event.broker_account_id, "broker_route": event.broker_route, "price": event.price, "quantity": event.quantity}
        if event.event_type is CanonicalExecutionEventType.ACKNOWLEDGED:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "SUBMITTED", **kwargs)
        elif event.event_type is CanonicalExecutionEventType.FILLED:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "FILLED", **kwargs)
        elif event.event_type is CanonicalExecutionEventType.PARTIAL_FILL:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "PARTIAL_FILL", **kwargs)
        else:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, event.event_type.value, **kwargs)
        return DispatchResult(applied, event.event_id, event.event_type)
