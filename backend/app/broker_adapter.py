from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

class BrokerOrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
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
    filled_quantity: float | None = None
    price: float | None = None
    message: str | None = None
    def __getitem__(self, key: str): return getattr(self, key)
    def get(self, key: str, default: Any = None): return getattr(self, key, default)
    def as_dict(self): return self.__dict__.copy()

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
    def find_order_by_client_id(self, client_order_id: str):
        get_orders = getattr(self, "get_orders", None)
        if get_orders is None: raise NotImplementedError("broker does not support client-order reconciliation")
        return next((dict(o) for o in get_orders() if str(o.get("client_order_id", "")) == client_order_id), None)

class PaperBrokerAdapter(BrokerAdapter):
    """Deterministic stateful paper broker: NEW -> PARTIALLY_FILLED -> FILLED/CANCELLED/REJECTED."""
    def __init__(self):
        self.orders = {}; self.positions = {}; self.next_id = 1
    def submit_order(self, order):
        if order.quantity <= 0: raise ValueError("quantity must be positive")
        cid = order.client_order_id if isinstance(order, BrokerOrderRequest) else f"client-{self.next_id}"
        existing = self.find_order_by_client_id(cid)
        if existing: return BrokerOrderUpdate(**existing)
        oid = f"PAPER-{self.next_id}"; self.next_id += 1
        record = {"order_id": oid, "status": "NEW", "client_order_id": cid, "symbol": order.symbol.upper(), "side": order.side.upper(), "quantity": order.quantity, "filled_quantity": 0, "price": order.price}
        self.orders[oid] = record
        return BrokerOrderUpdate(**record)
    def fill_order(self, broker_order_id, filled_quantity, price=None):
        record = self._open(broker_order_id)
        remaining = record["quantity"] - record["filled_quantity"]
        if filled_quantity <= 0 or filled_quantity > remaining: raise ValueError("invalid fill quantity")
        record["filled_quantity"] += filled_quantity; record["price"] = price if price is not None else record["price"]
        record["status"] = "FILLED" if record["filled_quantity"] == record["quantity"] else "PARTIALLY_FILLED"
        pos = self.positions.setdefault(record["symbol"], {"symbol": record["symbol"], "quantity": 0})
        pos["quantity"] += filled_quantity if record["side"] == "BUY" else -filled_quantity
        return BrokerOrderUpdate(**record)
    def reject_order(self, broker_order_id, message="broker rejected"):
        record = self._open(broker_order_id); record["status"] = "REJECTED"; record["message"] = message
        return BrokerOrderUpdate(**record)
    def cancel_order(self, broker_order_id):
        record = self._open(broker_order_id); record["status"] = "CANCELLED"
        return BrokerOrderUpdate(**record)
    def _open(self, broker_order_id):
        if broker_order_id not in self.orders: raise KeyError("order not found")
        record = self.orders[broker_order_id]
        if record["status"] in {"FILLED", "CANCELLED", "REJECTED"}: raise ValueError("order is terminal")
        return record
    def get_order(self, broker_order_id):
        if broker_order_id not in self.orders: raise KeyError("order not found")
        return self.orders[broker_order_id].copy()
    def get_orders(self): return [o.copy() for o in self.orders.values()]
    def get_positions(self): return [p.copy() for p in self.positions.values()]
    def get_account(self): return {"mode": "paper", "status": "READY"}
