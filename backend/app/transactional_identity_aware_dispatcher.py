from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher, DispatchResult
from app.canonical_execution_event import CanonicalExecutionEvent
from app.execution_identity_gateway import ExecutionIdentityGateway


@dataclass(frozen=True)
class TransactionalIdentityDispatchResult:
    dispatch: DispatchResult
    client_order_id: str


class TransactionalIdentityAwareDispatcher:
    """Live callback dispatcher using the single repository-backed identity source."""

    def __init__(self, dispatcher: CanonicalExecutionDispatcher, identity: ExecutionIdentityGateway) -> None:
        self.dispatcher = dispatcher
        self.identity = identity

    def dispatch(self, event: CanonicalExecutionEvent) -> TransactionalIdentityDispatchResult:
        resolved = self.identity.resolve(event)
        if resolved is None:
            raise LookupError(f"unknown broker order: {event.broker}:{event.broker_order_id}")
        if resolved.client_order_id != event.client_order_id:
            event = CanonicalExecutionEvent(event.event_id, event.broker_order_id, resolved.client_order_id, event.symbol, event.side, event.event_type, event.quantity, event.price, event.timestamp, event.broker)
        return TransactionalIdentityDispatchResult(self.dispatcher.dispatch(event), resolved.client_order_id)
