from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_event import CanonicalExecutionEvent
from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher, DispatchResult
from app.order_identity_registry import OrderIdentityRegistry


@dataclass(frozen=True)
class IdentityDispatchResult:
    dispatch: DispatchResult
    client_order_id: str


class IdentityAwareExecutionDispatcher:
    """Resolve broker callbacks to the internal order identity before dispatch."""

    def __init__(self, dispatcher: CanonicalExecutionDispatcher, registry: OrderIdentityRegistry) -> None:
        self.dispatcher = dispatcher
        self.registry = registry

    def dispatch(self, event: CanonicalExecutionEvent) -> IdentityDispatchResult:
        identity = self.registry.by_broker(event.broker, event.broker_order_id)
        if identity is None:
            raise LookupError(f"unknown broker order: {event.broker}:{event.broker_order_id}")
        if identity.client_order_id != event.client_order_id:
            event = CanonicalExecutionEvent(
                event_id=event.event_id,
                broker_order_id=event.broker_order_id,
                client_order_id=identity.client_order_id,
                symbol=event.symbol,
                side=event.side,
                event_type=event.event_type,
                quantity=event.quantity,
                price=event.price,
                timestamp=event.timestamp,
                broker=event.broker,
            )
        return IdentityDispatchResult(self.dispatcher.dispatch(event), identity.client_order_id)
