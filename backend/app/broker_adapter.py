from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class BrokerOrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class BrokerOrderRequest:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    stop: float | None = None
    target: float | None = None


@dataclass(frozen=True)
class BrokerOrderUpdate:
    client_order_id: str
    broker_order_id: str
    status: BrokerOrderStatus
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    message: str | None = None


@dataclass(frozen=True)
class BrokerOrder:
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    stop: float | None = None
    target: float | None = None


class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, order: BrokerOrderRequest | BrokerOrder) -> BrokerOrderUpdate: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate: ...

    @abstractmethod
    def get_order(self, broker_order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_account(self) -> dict[str, Any]: ...


class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self):
        self.orders: dict[str, dict[str, Any]] = {}
        self.positions: dict[str, dict[str, Any]] = {}
        self.next_id = 1

    def submit_order(self, order: BrokerOrderRequest | BrokerOrder) -> BrokerOrderUpdate:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")

        client_order_id = (
            order.client_order_id
            if isinstance(order, BrokerOrderRequest)
            else f"client-{self.next_id}"
        )
        oid = f"PAPER-{self.next_id}"
        self.next_id += 1

        record = {
            "client_order_id": client_order_id,
            "broker_order_id": oid,
            "status": BrokerOrderStatus.FILLED,
            "symbol": order.symbol.upper(),
            "side": order.side.upper(),
            "quantity": order.quantity,
            "price": order.price,
        }
        self.orders[oid] = record
        return BrokerOrderUpdate(**record)

    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        if broker_order_id not in self.orders:
            raise KeyError("order not found")
        self.orders[broker_order_id]["status"] = BrokerOrderStatus.CANCELLED
        record = self.orders[broker_order_id]
        return BrokerOrderUpdate(**record)

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        if broker_order_id not in self.orders:
            raise KeyError("order not found")
        return self.orders[broker_order_id].copy()

    def get_positions(self) -> list[dict[str, Any]]:
        return list(self.positions.values())

    def get_account(self) -> dict[str, Any]:
        return {"mode": "paper", "status": "READY"}
