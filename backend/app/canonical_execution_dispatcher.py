from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class DispatchResult:
    applied: bool
    event_id: str
    event_type: CanonicalExecutionEventType


class CanonicalExecutionDispatcher:
    """Translate canonical broker events into the single durable execution boundary."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def dispatch(self, event: CanonicalExecutionEvent) -> DispatchResult:
        if event.event_type is CanonicalExecutionEventType.ACKNOWLEDGED:
            # ACK is intentionally treated as an observation; no position mutation.
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "SUBMITTED")
        elif event.event_type is CanonicalExecutionEventType.FILLED:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "FILLED", price=event.price, quantity=event.quantity)
        elif event.event_type is CanonicalExecutionEventType.PARTIAL_FILL:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "PARTIAL_FILL", price=event.price, quantity=event.quantity)
        else:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, event.event_type.value, price=event.price, quantity=event.quantity)
        return DispatchResult(applied, event.event_id, event.event_type)
