from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite


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
    broker_account_id: int | None = None
    broker_route: str | None = None
    event_sequence: int | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.broker_order_id.strip() or not self.client_order_id.strip():
            raise ValueError("event_id, broker_order_id and client_order_id are required")
        if not isfinite(float(self.quantity)) or self.quantity < 0:
            raise ValueError("quantity must be finite and non-negative")
        if self.price is not None and (not isfinite(float(self.price)) or self.price < 0):
            raise ValueError("price must be finite and non-negative")
        if self.broker_account_id is not None and self.broker_account_id <= 0:
            raise ValueError("broker_account_id must be positive")
        if self.broker_account_id is not None and not self.broker_route:
            raise ValueError("broker_route is required with broker_account_id")
        if self.event_sequence is not None:
            if isinstance(self.event_sequence, bool) or not isinstance(self.event_sequence, int) or self.event_sequence < 0:
                raise ValueError("event_sequence must be a non-negative integer")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "side", self.side.upper())
