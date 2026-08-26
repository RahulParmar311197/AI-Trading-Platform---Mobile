from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any
import math
from threading import RLock

class BrokerOrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass(frozen=True)
class BrokerHealth:
    broker: str
    healthy: bool
    authenticated: bool = False
    live_trading_enabled: bool = False
    message: str = ""

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
    owner_user_id: int | None = None
    broker_account_id: int | None = None
    broker_route: str | None = None
    broker_route_generation: str | None = None

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
    average_price: float | None = None
    message: str | None = None
    def __getitem__(self, key: str): return getattr(self, key, None)
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

def normalize_broker_update(raw: BrokerOrderUpdate | dict[str, Any]) -> BrokerOrderUpdate:
    data = raw.as_dict() if isinstance(raw, BrokerOrderUpdate) else dict(raw)
    order_id = str(data.get("order_id") or data.get("broker_order_id") or "").strip()
    if not order_id: raise ValueError("broker response missing order_id")
    status = str(data.get("status") or "").strip().upper(); aliases = {"OPEN":"NEW","PENDING":"NEW","COMPLETE":"FILLED","EXECUTED":"FILLED","CANCELED":"CANCELLED","CANCEL":"CANCELLED","FAILED":"REJECTED"}; status = aliases.get(status,status)
    if status not in {s.value for s in BrokerOrderStatus}: raise ValueError(f"unsupported broker order status: {status}")
    quantity=data.get("quantity"); filled=data.get("filled_quantity")
    if quantity is not None and (not math.isfinite(float(quantity)) or float(quantity)<0): raise ValueError("invalid broker quantity")
    if filled is not None and (not math.isfinite(float(filled)) or float(filled)<0): raise ValueError("invalid broker filled quantity")
    if quantity is not None and filled is not None and float(filled)>float(quantity)+1e-9: raise ValueError("broker filled quantity exceeds order quantity")
    return BrokerOrderUpdate(order_id=order_id,status=status,client_order_id=data.get("client_order_id"),symbol=str(data["symbol"]).upper() if data.get("symbol") else None,side=str(data["side"]).upper() if data.get("side") else None,quantity=float(quantity) if quantity is not None else None,filled_quantity=float(filled) if filled is not None else None,price=float(data["price"]) if data.get("price") is not None else None,average_price=float(data["average_price"]) if data.get("average_price") is not None else None,message=data.get("message"))

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
    def health(self) -> BrokerHealth:
        return BrokerHealth(broker=self.__class__.__name__, healthy=False, message="broker health capability not implemented")
    def find_order_by_client_id(self, client_order_id: str):
        get_orders=getattr(self,"get_orders",None)
        if get_orders is None: raise NotImplementedError("broker does not support client-order reconciliation")
        matches=[dict(o) for o in get_orders() if str(o.get("client_order_id",""))==client_order_id]
        if len(matches)>1: raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
        return matches[0] if matches else None

class PaperBrokerAdapter(BrokerAdapter):
    """Deterministic in-memory adapter for paper execution and reconciliation tests."""
    def __init__(self):
        self._lock=RLock(); self._orders={}; self._positions={}; self._sequence=0
    def _new_id(self):
        self._sequence += 1; return f"PAPER-{self._sequence:08d}"
    @staticmethod
    def _validate(symbol, side, quantity):
        symbol=str(symbol or "").strip().upper(); side=str(side or "").strip().upper(); quantity=float(quantity)
        if not symbol: raise ValueError("symbol is required")
        if side not in {"BUY","SELL"}: raise ValueError("side must be BUY or SELL")
        if not math.isfinite(quantity) or quantity<=0: raise ValueError("quantity must be positive and finite")
        return symbol,side,quantity
    def submit_order(self, order):
        symbol,side,quantity=self._validate(order.symbol,order.side,order.quantity); client_id=getattr(order,"client_order_id",None)
        with self._lock:
            if client_id:
                existing=self.find_order_by_client_id(client_id)
                if existing is not None: return dict(existing)
            oid=self._new_id(); price=float(order.price) if getattr(order,"price",None) is not None else 0.0
            record={"order_id":oid,"broker_order_id":oid,"client_order_id":client_id,"symbol":symbol,"side":side,"quantity":quantity,"filled_quantity":quantity,"status":"FILLED","price":price,"average_price":price}
            self._orders[oid]=record; self._positions[symbol]=self._positions.get(symbol,0.0)+(quantity if side=="BUY" else -quantity)
            return dict(record)
    def cancel_order(self, broker_order_id):
        with self._lock:
            record=self._orders.get(str(broker_order_id))
            if record is None: raise ValueError("unknown broker order")
            if record["status"] != "FILLED": record["status"]="CANCELLED"
            return dict(record)
    def get_order(self, broker_order_id):
        with self._lock:
            record=self._orders.get(str(broker_order_id))
            if record is None: raise ValueError("unknown broker order")
            return dict(record)
    def get_orders(self):
        with self._lock: return [dict(order) for order in self._orders.values()]
    def get_positions(self):
        with self._lock: return [{"symbol":s,"quantity":q} for s,q in self._positions.items() if q != 0]
    def get_account(self):
        return {"mode":"paper","healthy":True,"authenticated":True,"live_trading_enabled":False}
    def health(self):
        return BrokerHealth(broker=self.__class__.__name__,healthy=True,authenticated=True,live_trading_enabled=False,message="paper broker")
