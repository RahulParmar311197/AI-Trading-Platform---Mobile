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
    security_id: str = ""
    exchange_segment: str = "NSE_EQ"
    product_type: str = "CNC"
    validity: str = "DAY"
    trigger_price: float | None = None


@dataclass(frozen=True)
class BrokerOrderUpdate:
    order_id: str
    status: str
    client_order_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    quantity: float | None = None
    price: float | None = None
    message: str | None = None

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default: Any = None):
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "message": self.message,
        }


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

    def find_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        """Return the broker order for a client id, or None when not found.

        Adapters with a native client-order-id lookup should override this method.
        The default implementation preserves compatibility by scanning snapshots.
        """
        get_orders = getattr(self, "get_orders", None)
        if get_orders is None:
            raise NotImplementedError("broker does not support client-order reconciliation")
        for order in get_orders():
            if str(order.get("client_order_id", "")) == client_order_id:
                return dict(order)
        return None


class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self):
        self.orders: dict[str, dict[str, Any]] = {}
        self.positions: dict[str, dict[str, Any]] = {}
        self.next_id = 1

    def submit_order(self, order: BrokerOrderRequest | BrokerOrder) -> BrokerOrderUpdate:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        client_order_id = order.client_order_id if isinstance(order, BrokerOrderRequest) else f"client-{self.next_id}"
        oid = f"PAPER-{self.next_id}"
        self.next_id += 1
        record = {"order_id": oid, "status": BrokerOrderStatus.FILLED.value, "client_order_id": client_order_id, "symbol": order.symbol.upper(), "side": order.side.upper(), "quantity": order.quantity, "price": order.price}
        self.orders[oid] = record
        return BrokerOrderUpdate(**record)

    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        if broker_order_id not in self.orders:
            raise KeyError("order not found")
        self.orders[broker_order_id]["status"] = BrokerOrderStatus.CANCELLED.value
        return BrokerOrderUpdate(**self.orders[broker_order_id])

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        if broker_order_id not in self.orders:
            raise KeyError("order not found")
        return self.orders[broker_order_id].copy()

    def get_orders(self) -> list[dict[str, Any]]:
        return [order.copy() for order in self.orders.values()]

    def get_positions(self) -> list[dict[str, Any]]:
        return [position.copy() for position in self.positions.values()]

    def get_account(self) -> dict[str, Any]:
        return {"mode": "paper", "status": "READY"}
