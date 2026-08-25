from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BrokerOrderState(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BrokerOrderRequest:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    limit_price: float | None = None
    stop_price: float | None = None


@dataclass(frozen=True)
class BrokerOrderResult:
    client_order_id: str
    broker_order_id: str | None
    state: BrokerOrderState
    accepted_quantity: float = 0.0
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    message: str = ""
    raw: Any = None


class BrokerExecutionError(RuntimeError):
    """Normalized broker execution failure."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable
