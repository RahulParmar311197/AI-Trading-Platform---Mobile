from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher, DispatchResult
from app.canonical_execution_event import CanonicalExecutionEvent
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.execution_identity_gateway import ExecutionIdentityGateway


@dataclass(frozen=True)
class TransactionalQuarantineDispatchResult:
    dispatched: bool
    quarantined: bool
    event_id: str
    dispatch: DispatchResult | None = None


class TransactionalQuarantiningDispatcher:
    """Fail closed while resolving identity through the single execution repository."""

    def __init__(self, dispatcher: CanonicalExecutionDispatcher, identity: ExecutionIdentityGateway, quarantine: ExecutionEventQuarantine) -> None:
        self.dispatcher = dispatcher
        self.identity = identity
        self.quarantine = quarantine

    def dispatch(self, event: CanonicalExecutionEvent) -> TransactionalQuarantineDispatchResult:
        resolved = self.identity.resolve(event)
        if resolved is None:
            inserted = self.quarantine.quarantine(
                event_id=event.event_id,
                broker=event.broker,
                broker_order_id=event.broker_order_id,
                payload={"client_order_id": event.client_order_id, "symbol": event.symbol, "side": event.side, "event_type": event.event_type.value, "quantity": event.quantity, "price": event.price},
                reason="UNKNOWN_BROKER_ORDER",
            )
            return TransactionalQuarantineDispatchResult(False, inserted, event.event_id)
        if resolved.client_order_id != event.client_order_id:
            event = CanonicalExecutionEvent(event.event_id, event.broker_order_id, resolved.client_order_id, event.symbol, event.side, event.event_type, event.quantity, event.price, event.timestamp, event.broker)
        result = self.dispatcher.dispatch(event)
        return TransactionalQuarantineDispatchResult(True, False, event.event_id, result)
