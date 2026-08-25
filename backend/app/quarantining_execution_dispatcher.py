from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher, DispatchResult
from app.canonical_execution_event import CanonicalExecutionEvent
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentityRegistry


@dataclass(frozen=True)
class QuarantineDispatchResult:
    dispatched: bool
    quarantined: bool
    event_id: str
    dispatch: DispatchResult | None = None


class QuarantiningExecutionDispatcher:
    """Fail closed while preserving unresolved broker events for recovery."""

    def __init__(self, dispatcher: CanonicalExecutionDispatcher, registry: OrderIdentityRegistry, quarantine: ExecutionEventQuarantine) -> None:
        self.dispatcher = dispatcher
        self.registry = registry
        self.quarantine = quarantine

    def dispatch(self, event: CanonicalExecutionEvent) -> QuarantineDispatchResult:
        identity = self.registry.by_broker(event.broker, event.broker_order_id)
        if identity is None:
            inserted = self.quarantine.quarantine(
                event_id=event.event_id,
                broker=event.broker,
                broker_order_id=event.broker_order_id,
                payload={"client_order_id": event.client_order_id, "symbol": event.symbol, "side": event.side, "event_type": event.event_type.value, "quantity": event.quantity, "price": event.price},
                reason="UNKNOWN_BROKER_ORDER",
            )
            return QuarantineDispatchResult(False, inserted, event.event_id)
        if identity.client_order_id != event.client_order_id:
            event = CanonicalExecutionEvent(event.event_id, event.broker_order_id, identity.client_order_id, event.symbol, event.side, event.event_type, event.quantity, event.price, event.timestamp, event.broker)
        result = self.dispatcher.dispatch(event)
        return QuarantineDispatchResult(True, False, event.event_id, result)
