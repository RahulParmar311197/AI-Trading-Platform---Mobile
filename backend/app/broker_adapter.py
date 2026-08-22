from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

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
    def submit_order(self, order: BrokerOrder) -> dict[str, Any]: ...
    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> dict[str, Any]: ...
    @abstractmethod
    def get_order(self, broker_order_id: str) -> dict[str, Any]: ...
    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...
    @abstractmethod
    def get_account(self) -> dict[str, Any]: ...

class PaperBrokerAdapter(BrokerAdapter):
    def __init__(self):
        self.orders={}; self.positions={}; self.next_id=1
    def submit_order(self, order: BrokerOrder):
        if order.quantity <= 0: raise ValueError("quantity must be positive")
        oid=f"PAPER-{self.next_id}"; self.next_id+=1
        self.orders[oid]={"broker_order_id":oid,"status":"FILLED","symbol":order.symbol.upper(),"side":order.side.upper(),"quantity":order.quantity,"price":order.price}
        return self.orders[oid].copy()
    def cancel_order(self, broker_order_id):
        if broker_order_id not in self.orders: raise KeyError("order not found")
        self.orders[broker_order_id]["status"]="CANCELLED"; return self.orders[broker_order_id].copy()
    def get_order(self, broker_order_id):
        if broker_order_id not in self.orders: raise KeyError("order not found")
        return self.orders[broker_order_id].copy()
    def get_positions(self): return list(self.positions.values())
    def get_account(self): return {"mode":"paper","status":"READY"}
