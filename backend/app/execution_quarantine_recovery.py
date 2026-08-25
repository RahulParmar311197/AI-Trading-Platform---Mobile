from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentityRegistry


@dataclass(frozen=True)
class RecoveryResult:
    attempted: int
    recovered: int
    remaining: int


class ExecutionQuarantineRecovery:
    """Retry unresolved events only after broker identity becomes resolvable."""

    def __init__(self, registry: OrderIdentityRegistry, quarantine: ExecutionEventQuarantine, dispatcher: CanonicalExecutionDispatcher) -> None:
        self.registry = registry
        self.quarantine = quarantine
        self.dispatcher = dispatcher

    def recover(self, limit: int = 100) -> RecoveryResult:
        items = self.quarantine.pending(limit)
        recovered = 0
        for item in items:
            payload = item["payload"]
            account_id = payload.get("broker_account_id")
            route = payload.get("broker_route")
            if account_id is None or not route:
                continue
            identity = self.registry.by_broker(item["broker"], item["broker_order_id"], broker_account_id=int(account_id), broker_route=str(route))
            if identity is None:
                continue
            event = CanonicalExecutionEvent(
                event_id=item["event_id"],
                broker_order_id=item["broker_order_id"],
                client_order_id=identity.client_order_id,
                symbol=payload["symbol"],
                side=payload["side"],
                event_type=CanonicalExecutionEventType(payload["event_type"]),
                quantity=float(payload.get("quantity", 0)),
                price=payload.get("price"),
                broker=item["broker"],
                broker_account_id=int(account_id),
                broker_route=str(route),
            )
            result = self.dispatcher.dispatch(event)
            if result.applied:
                self.quarantine.resolve(item["id"])
                recovered += 1
        remaining = len(self.quarantine.pending(limit))
        return RecoveryResult(len(items), recovered, remaining)
