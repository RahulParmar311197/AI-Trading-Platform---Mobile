from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.execution_lifecycle import ExecutionLedger, OrderStatus


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    order_id: str
    kind: str
    price: float | None = None
    quantity: float = 0.0


class IdempotentExecutionEventProcessor:
    """Apply broker callbacks exactly once by durable event identity."""

    def __init__(self, ledger: ExecutionLedger) -> None:
        self.ledger = ledger
        self._lock = RLock()
        self._processed: set[str] = set()

    def process(self, event: ExecutionEvent):
        if not event.event_id:
            raise ValueError("event_id is required")
        with self._lock:
            if event.event_id in self._processed:
                return False
            result = self._apply(event)
            self._processed.add(event.event_id)
            return result

    def _apply(self, event: ExecutionEvent):
        kind = event.kind.upper()
        if kind == "SUBMITTED":
            return self.ledger.transition(event.order_id, OrderStatus.SUBMITTED)
        if kind == "ACKNOWLEDGED":
            return self.ledger.orders[event.order_id]
        if kind == "PARTIAL_FILL":
            return self.ledger.fill(event.order_id, float(event.price), event.quantity)
        if kind == "FILLED":
            return self.ledger.fill(event.order_id, float(event.price), event.quantity)
        if kind == "CANCELLED":
            return self.ledger.transition(event.order_id, OrderStatus.CANCELLED)
        if kind == "REJECTED":
            return self.ledger.transition(event.order_id, OrderStatus.REJECTED)
        raise ValueError(f"unsupported execution event: {event.kind}")
