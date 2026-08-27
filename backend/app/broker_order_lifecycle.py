from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


_TERMINAL = {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED}
_ALLOWED = {
    OrderStatus.SUBMITTED: {OrderStatus.ACCEPTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED},
    OrderStatus.FILLED: set(), OrderStatus.REJECTED: set(), OrderStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class OrderLifecycleEvent:
    status: OrderStatus
    timestamp: datetime
    broker_order_id: str | None = None
    filled_quantity: int = 0
    average_price: float | None = None
    reason: str | None = None


class InvalidOrderTransition(ValueError):
    pass


@dataclass
class OrderLifecycle:
    status: OrderStatus = OrderStatus.SUBMITTED
    filled_quantity: int = 0
    average_price: float | None = None
    events: list[OrderLifecycleEvent] | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL

    def apply(self, event: OrderLifecycleEvent) -> None:
        if event.status not in _ALLOWED[self.status]:
            raise InvalidOrderTransition(f"cannot transition {self.status.value} -> {event.status.value}")
        if event.filled_quantity < self.filled_quantity:
            raise InvalidOrderTransition("filled quantity cannot decrease")
        self.status = event.status
        self.filled_quantity = event.filled_quantity
        if event.average_price is not None:
            self.average_price = event.average_price
        self.events.append(event)
