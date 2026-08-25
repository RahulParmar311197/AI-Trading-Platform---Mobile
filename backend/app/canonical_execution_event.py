from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CanonicalExecutionEventType(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CanonicalExecutionEvent:
    event_id: str
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: str
    event_type: CanonicalExecutionEventType
    quantity: float = 0.0
    price: float | None = None
    timestamp: datetime | None = None
    broker: str = ""

    def __post_init__(self) -> None:
        if not self.event_id or not self.broker_order_id or not self.client_order_id:
            raise ValueError("event_id, broker_order_id and client_order_id are required")
        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")
        if self.price is not None and self.price < 0:
            raise ValueError("price cannot be negative")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "side", self.side.upper())
