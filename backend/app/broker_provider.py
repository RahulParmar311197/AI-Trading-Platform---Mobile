from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class BrokerOrder:
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: float | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class BrokerOrderResult:
    broker_order_id: str
    status: str


class BrokerProvider(Protocol):
    """Provider contract; implementations must never bypass RiskGateway."""

    def health(self) -> bool: ...
    def account(self) -> dict: ...
    def positions(self) -> list[dict]: ...
    def orders(self) -> list[dict]: ...
    def place_order(self, order: BrokerOrder) -> BrokerOrderResult: ...
    def cancel_order(self, broker_order_id: str) -> bool: ...
    def modify_order(self, broker_order_id: str, *, quantity: int | None = None, price: float | None = None) -> BrokerOrderResult: ...
