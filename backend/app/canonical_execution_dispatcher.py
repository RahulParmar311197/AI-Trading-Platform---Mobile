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
        if event.broker_account_id is None or not event.broker_route:
            raise ValueError("broker account identity is required for execution dispatch")
        kwargs = {
            "broker_account_id": event.broker_account_id,
            "broker_route": event.broker_route,
            "price": event.price,
            "quantity": event.quantity,
        }
        if event.event_type is CanonicalExecutionEventType.ACKNOWLEDGED:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "SUBMITTED", **kwargs)
        elif event.event_type is CanonicalExecutionEventType.FILLED:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "FILLED", **kwargs)
        elif event.event_type is CanonicalExecutionEventType.PARTIAL_FILL:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, "PARTIAL_FILL", **kwargs)
        else:
            applied = self.repository.apply_event(event.event_id, event.client_order_id, event.event_type.value, **kwargs)
        return DispatchResult(applied, event.event_id, event.event_type)
