from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import math


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
    filled_quantity: float = 0
    average_price: float | None = None
    reason: str | None = None


class InvalidOrderTransition(ValueError):
    pass


@dataclass
class OrderLifecycle:
    status: OrderStatus = OrderStatus.SUBMITTED
    requested_quantity: float | None = None
    filled_quantity: float = 0
    average_price: float | None = None
    events: list[OrderLifecycleEvent] | None = None
    broker_order_id: str | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []
        if self.requested_quantity is not None:
            try:
                quantity = float(self.requested_quantity)
            except (TypeError, ValueError):
                raise ValueError("requested quantity must be finite and positive")
            if not math.isfinite(quantity) or quantity <= 0:
                raise ValueError("requested quantity must be finite and positive")
            self.requested_quantity = quantity
        if not math.isfinite(float(self.filled_quantity)) or float(self.filled_quantity) < 0:
            raise ValueError("filled quantity must be finite and non-negative")
        if self.requested_quantity is not None and float(self.filled_quantity) > self.requested_quantity + 1e-9:
            raise ValueError("filled quantity cannot exceed requested quantity")
        if self.broker_order_id is not None:
            broker_order_id = str(self.broker_order_id).strip()
            if not broker_order_id:
                raise ValueError("broker order id must be non-empty")
            self.broker_order_id = broker_order_id

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL

    def apply(self, event: OrderLifecycleEvent) -> None:
        if event.status not in _ALLOWED[self.status]:
            raise InvalidOrderTransition(f"cannot transition {self.status.value} -> {event.status.value}")
        try:
            filled = float(event.filled_quantity)
        except (TypeError, ValueError):
            raise InvalidOrderTransition("filled quantity must be finite and non-negative")
        if not math.isfinite(filled) or filled < 0:
            raise InvalidOrderTransition("filled quantity must be finite and non-negative")
        if filled < float(self.filled_quantity):
            raise InvalidOrderTransition("filled quantity cannot decrease")
        if self.requested_quantity is not None and filled > self.requested_quantity + 1e-9:
            raise InvalidOrderTransition("filled quantity cannot exceed requested quantity")
        if self.events and event.timestamp < self.events[-1].timestamp:
            raise InvalidOrderTransition("lifecycle event timestamp cannot move backwards")
        if event.average_price is not None:
            try:
                average_price = float(event.average_price)
            except (TypeError, ValueError):
                raise InvalidOrderTransition("average price must be finite and positive")
            if not math.isfinite(average_price) or average_price <= 0:
                raise InvalidOrderTransition("average price must be finite and positive")
        event_broker_order_id = None
        if event.broker_order_id is not None:
            event_broker_order_id = str(event.broker_order_id).strip()
            if not event_broker_order_id:
                raise InvalidOrderTransition("broker order id must be non-empty")
            if self.broker_order_id is not None and event_broker_order_id != self.broker_order_id:
                raise InvalidOrderTransition("broker order id cannot change during lifecycle")
        self.status = event.status
        self.filled_quantity = filled
        if event.average_price is not None:
            self.average_price = float(event.average_price)
        if event_broker_order_id is not None:
            self.broker_order_id = event_broker_order_id
        self.events.append(event)
