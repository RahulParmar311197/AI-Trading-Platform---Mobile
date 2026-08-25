from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.execution_identity_gateway import ExecutionIdentityGateway


@dataclass(frozen=True)
class TransactionalRecoveryResult:
    attempted: int
    recovered: int
    remaining: int


class TransactionalQuarantineRecovery:
    """Recover events using the same repository-backed identity path as live callbacks."""

    def __init__(self, identity: ExecutionIdentityGateway, quarantine: ExecutionEventQuarantine, dispatcher: CanonicalExecutionDispatcher) -> None:
        self.identity = identity
        self.quarantine = quarantine
        self.dispatcher = dispatcher

    def recover(self, limit: int = 100) -> TransactionalRecoveryResult:
        items = self.quarantine.pending(limit)
        recovered = 0
        for item in items:
            event = CanonicalExecutionEvent(
                event_id=item["event_id"],
                broker_order_id=item["broker_order_id"],
                client_order_id="",
                symbol=item["payload"]["symbol"],
                side=item["payload"]["side"],
                event_type=CanonicalExecutionEventType(item["payload"]["event_type"]),
                quantity=float(item["payload"].get("quantity", 0)),
                price=item["payload"].get("price"),
                broker=item["broker"],
            )
            resolved = self.identity.resolve(event)
            if resolved is None:
                continue
            event = CanonicalExecutionEvent(event.event_id, event.broker_order_id, resolved.client_order_id, event.symbol, event.side, event.event_type, event.quantity, event.price, event.timestamp, event.broker)
            result = self.dispatcher.dispatch(event)
            if result.applied:
                self.quarantine.resolve(item["id"])
                recovered += 1
        return TransactionalRecoveryResult(len(items), recovered, len(self.quarantine.pending(limit)))
