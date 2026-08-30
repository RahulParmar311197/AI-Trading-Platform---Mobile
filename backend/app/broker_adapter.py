from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any
import math
from threading import RLock

from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_position_snapshot import BrokerPositionSnapshot

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
    broker_account_id: str | None = None
    broker_route: str | None = None
    broker_route_generation: str | None = None
    def __post_init__(self):
        if self.broker_account_id is None: return
        if isinstance(self.broker_account_id, bool): raise ValueError("broker_account_id must be a non-empty string")
        value = str(self.broker_account_id).strip()
        if not value: raise ValueError("broker_account_id must be a non-empty string")
        if len(value) > 128: raise ValueError("broker_account_id exceeds 128 characters")
        object.__setattr__(self, "broker_account_id", value)

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
    broker_account_id: str | None = None
    broker_route: str | None = None
    broker_route_generation: str | None = None
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

def _finite_optional(value: Any, field: str) -> float | None:
    if value is None or value == "": return None
    number = float(value)
    if not math.isfinite(number): raise ValueError(f"invalid broker {field}")
    return number

def _optional_identity(value: Any, field: str) -> str | None:
    if value is None or value == "": return None
    identity = str(value).strip()
    if not identity: raise ValueError(f"invalid broker {field}")
    return identity

def normalize_broker_update(raw: BrokerOrderUpdate | dict[str, Any], *, expected: BrokerOrderRequest | None = None) -> BrokerOrderUpdate:
    data = raw.as_dict() if isinstance(raw, BrokerOrderUpdate) else dict(raw)
    order_id = str(data.get("order_id") or data.get("broker_order_id") or "").strip()
    if not order_id: raise ValueError("broker response missing order_id")
    status = str(data.get("status") or "").strip().upper()
    status = {"OPEN":"NEW","PENDING":"NEW","COMPLETE":"FILLED","EXECUTED":"FILLED","CANCELED":"CANCELLED","CANCEL":"CANCELLED","FAILED":"REJECTED"}.get(status, status)
    if status not in {s.value for s in BrokerOrderStatus}: raise ValueError(f"unsupported broker order status: {status}")
    quantity = _finite_optional(data.get("quantity"), "quantity"); filled = _finite_optional(data.get("filled_quantity"), "filled quantity"); price = _finite_optional(data.get("price"), "price"); average = _finite_optional(data.get("average_price"), "average price")
    if quantity is not None and quantity < 0: raise ValueError("invalid broker quantity")
    if filled is not None and filled < 0: raise ValueError("invalid broker filled quantity")
    if quantity is not None and filled is not None and filled > quantity + 1e-9: raise ValueError("broker filled quantity exceeds order quantity")
    client_id = str(data.get("client_order_id") if data.get("client_order_id") is not None else data.get("tag")).strip() if data.get("client_order_id") is not None or data.get("tag") is not None else None
    symbol = str(data.get("symbol") or data.get("trading_symbol") or "").strip().upper() or None
    side = str(data.get("side") or data.get("transaction_type") or "").strip().upper() or None
    broker_account_id = _optional_identity(data.get("broker_account_id") if data.get("broker_account_id") is not None else data.get("account_id"), "account identity")
    broker_route = _optional_identity(data.get("broker_route") if data.get("broker_route") is not None else data.get("route"), "route identity")
    broker_route_generation = _optional_identity(data.get("broker_route_generation") if data.get("broker_route_generation") is not None else data.get("route_generation"), "route generation")
    if expected is not None:
        if client_id is None or client_id != expected.client_order_id: raise ValueError("broker client_order_id does not match request")
        if symbol is None or symbol != expected.symbol.upper(): raise ValueError("broker symbol does not match request")
        if side is None or side != expected.side.upper(): raise ValueError("broker side does not match request")
        if quantity is None: raise ValueError("broker response missing requested quantity")
        if expected.broker_account_id is not None and (broker_account_id is None or broker_account_id != expected.broker_account_id): raise ValueError("broker account does not match request")
        if expected.broker_route is not None and (broker_route is None or broker_route != expected.broker_route): raise ValueError("broker route does not match request")
        if expected.broker_route_generation is not None and (broker_route_generation is None or broker_route_generation != expected.broker_route_generation): raise ValueError("broker route generation does not match request")
    if price is not None and price <= 0: raise ValueError("broker price must be positive")
    if average is not None and average <= 0: raise ValueError("broker average price must be positive")
    if status == "NEW" and filled is not None and abs(filled) > 1e-9: raise ValueError("NEW broker status requires zero filled quantity")
    if status == "PARTIALLY_FILLED" and (quantity is None or filled is None or not (0 < filled < quantity)): raise ValueError("PARTIALLY_FILLED broker status requires 0 < filled < quantity")
    if status == "FILLED" and (quantity is None or filled is None or abs(filled - quantity) > 1e-9): raise ValueError("FILLED broker status requires filled quantity equal to quantity")
    if status == "REJECTED" and filled is not None and abs(filled) > 1e-9: raise ValueError("REJECTED broker status requires zero filled quantity")
    if status in {"PARTIALLY_FILLED", "FILLED"} and (filled is None or filled <= 0): raise ValueError("filled broker status requires positive filled quantity")
    if filled is not None and filled > 0 and average is None: raise ValueError("non-zero broker fill requires average_price")
    return BrokerOrderUpdate(order_id=order_id,status=status,client_order_id=client_id,symbol=symbol,side=side,quantity=quantity,filled_quantity=filled,price=price,average_price=average,broker_account_id=broker_account_id,broker_route=broker_route,broker_route_generation=broker_route_generation,message=data.get("message"))

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
    def health(self) -> BrokerHealth: return BrokerHealth(broker=self.__class__.__name__, healthy=False, message="broker health capability not implemented")
    def get_order_snapshot(self) -> BrokerOrderSnapshot:
        get_orders = getattr(self, "get_orders", None)
        if get_orders is None: raise NotImplementedError("broker does not support authoritative order snapshots")
        orders = get_orders()
        if not isinstance(orders, list): raise RuntimeError("broker order snapshot is invalid")
        return BrokerOrderSnapshot(orders=[dict(o) for o in orders], complete=False, source=self.__class__.__name__)
    def get_position_snapshot(self) -> BrokerPositionSnapshot:
        positions = self.get_positions()
        if not isinstance(positions, list): raise RuntimeError("broker position snapshot is invalid")
        return BrokerPositionSnapshot(positions=[dict(p) for p in positions], complete=False, source=self.__class__.__name__)
    def find_order_by_client_id(self, client_order_id: str):
        snapshot = self.get_order_snapshot().require_authoritative(); matches=[dict(o) for o in snapshot if str(o.get("client_order_id",o.get("tag","")))==client_order_id]
        if len(matches)>1: raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
        return matches[0] if matches else None

class PaperBrokerAdapter(BrokerAdapter):
    """Deterministic in-memory adapter for paper execution and reconciliation tests."""
    def __init__(self): self._lock=RLock(); self._orders={}; self._positions={}; self._sequence=0
    def _new_id(self): self._sequence += 1; return f"PAPER-{self._sequence:08d}"
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
            self._orders[oid]=record; self._positions[symbol]=self._positions.get(symbol,0.0)+(quantity if side=="BUY" else -quantity); return dict(record)
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
    def get_order_snapshot(self): return BrokerOrderSnapshot(orders=self.get_orders(), complete=True, source=self.__class__.__name__)
    def get_positions(self):
        with self._lock: return [{"symbol":s,"quantity":q} for s,q in self._positions.items() if q != 0]
    def get_position_snapshot(self): return BrokerPositionSnapshot(positions=self.get_positions(), complete=True, source=self.__class__.__name__)
    def get_account(self): return {"mode":"paper","healthy":True,"authenticated":True,"live_trading_enabled":False}
    def health(self): return BrokerHealth(broker=self.__class__.__name__,healthy=True,authenticated=True,live_trading_enabled=False,message="paper broker")

class UpstoxAdapter(BrokerAdapter):
    """Request-safe Upstox boundary around an injected SDK/HTTP client."""
    def __init__(self, client: Any, *, broker_account_id: str, broker_route_generation: str, broker_route: str = "upstox"):
        if not str(broker_account_id).strip(): raise ValueError("broker_account_id is required")
        if not str(broker_route).strip(): raise ValueError("broker_route is required")
        if not str(broker_route_generation).strip(): raise ValueError("broker_route_generation is required")
        self.client=client; self.broker_account_id=str(broker_account_id).strip(); self.broker_route=str(broker_route).strip(); self.broker_route_generation=str(broker_route_generation).strip()
    @staticmethod
    def _call(client,name,*args,**kwargs):
        method=getattr(client,name,None)
        if not callable(method): raise NotImplementedError(f"Upstox client missing required method: {name}")
        return method(*args,**kwargs)
    @staticmethod
    def _data(raw): return raw.get("data") if isinstance(raw,dict) and "data" in raw else raw
    def _payload(self,order: BrokerOrderRequest)->dict[str,Any]:
        if not isinstance(order,BrokerOrderRequest): raise TypeError("UpstoxAdapter requires BrokerOrderRequest")
        if order.broker_account_id != self.broker_account_id: raise ValueError("broker account does not match Upstox adapter")
        if order.broker_route not in {None,self.broker_route}: raise ValueError("broker route does not match Upstox adapter")
        if order.broker_route_generation not in {None,self.broker_route_generation}: raise ValueError("broker route generation does not match Upstox adapter")
        if not order.security_id.strip(): raise ValueError("Upstox security_id/instrument_token is required")
        quantity=float(order.quantity)
        if not math.isfinite(quantity) or quantity<=0 or quantity!=int(quantity): raise ValueError("Upstox quantity must be a positive integer")
        product={"CNC":"D","DELIVERY":"D","INTRADAY":"I","I":"I","D":"D","MTF":"MTF"}.get(order.product_type.upper())
        if product is None: raise ValueError(f"unsupported Upstox product_type: {order.product_type}")
        order_type=order.order_type.upper()
        if order_type not in {"MARKET","LIMIT","SL","SL-M"}: raise ValueError(f"unsupported Upstox order_type: {order.order_type}")
        validity=order.validity.upper()
        if validity not in {"DAY","IOC"}: raise ValueError(f"unsupported Upstox validity: {order.validity}")
        payload={"quantity":int(quantity),"product":product,"validity":validity,"price":float(order.price or 0),"tag":order.client_order_id,"instrument_token":order.security_id,"order_type":order_type,"transaction_type":order.side.upper(),"disclosed_quantity":0,"trigger_price":float(order.trigger_price or order.stop or 0),"is_amo":False,"market_protection":0}
        if order_type=="MARKET": payload["price"]=0
        return payload
    def _normalize(self,raw:Any,*,expected:BrokerOrderRequest|None=None)->BrokerOrderUpdate:
        data=dict(self._data(raw) or {})
        if isinstance(data,list):
            if len(data)!=1: raise ValueError("Upstox order response is ambiguous")
            data=dict(data[0])
        data["broker_account_id"]=self.broker_account_id; data["broker_route"]=self.broker_route; data["broker_route_generation"]=self.broker_route_generation
        data.setdefault("client_order_id",data.get("tag")); data.setdefault("symbol",data.get("trading_symbol") or (expected.symbol if expected else None)); data.setdefault("side",data.get("transaction_type") or (expected.side if expected else None))
        return normalize_broker_update(data,expected=expected)
    def submit_order(self,order):
        raw=self._call(self.client,"place_order",self._payload(order)); data=dict(self._data(raw) or {}); order_id=str(data.get("order_id") or "").strip()
        if not order_id: raise RuntimeError("Upstox place_order response missing order_id")
        details=self.get_order(order_id) if callable(getattr(self.client,"get_order",None)) else {**data,"status":"NEW","order_id":order_id}
        return self._normalize(details,expected=order)
    def cancel_order(self,broker_order_id:str)->BrokerOrderUpdate:
        raw=self._call(self.client,"cancel_order",str(broker_order_id)); data=dict(self._data(raw) or {}); data.setdefault("order_id",broker_order_id); data.setdefault("status","CANCELLED"); return self._normalize(data)
    def get_order(self,broker_order_id:str)->dict[str,Any]:
        raw=self._call(self.client,"get_order",str(broker_order_id)); data=dict(self._data(raw) or {}); data["broker_account_id"]=self.broker_account_id; data["broker_route"]=self.broker_route; data["broker_route_generation"]=self.broker_route_generation; return data
    def get_orders(self)->list[dict[str,Any]]:
        raw=self._call(self.client,"get_orders"); data=self._data(raw)
        if not isinstance(data,list): raise RuntimeError("Upstox order book response is invalid")
        result=[]
        for order in data:
            item=dict(order); item["broker_account_id"]=self.broker_account_id; item["broker_route"]=self.broker_route; item["broker_route_generation"]=self.broker_route_generation; item.setdefault("client_order_id",item.get("tag")); result.append(item)
        return result
    def find_order_by_client_id(self,client_order_id:str):
        matches=[o for o in self.get_orders() if str(o.get("client_order_id") or o.get("tag") or "").strip()==client_order_id]
        if len(matches)>1: raise RuntimeError(f"ambiguous Upstox order identity for client_order_id: {client_order_id}")
        return self._normalize(matches[0]) if matches else None
    def get_positions(self)->list[dict[str,Any]]:
        raw=self._call(self.client,"get_positions"); data=self._data(raw)
        if not isinstance(data,list): raise RuntimeError("Upstox positions response is invalid")
        return [dict(position) for position in data]
    def get_account(self)->dict[str,Any]:
        raw=self._call(self.client,"get_profile"); data=dict(self._data(raw) or {}); account_id=str(data.get("user_id") or data.get("userId") or "").strip()
        if account_id and account_id!=self.broker_account_id: raise RuntimeError("Upstox profile account identity does not match configured broker account")
        data["broker_account_id"]=self.broker_account_id; return data
    def health(self)->BrokerHealth:
        try:
            account=self.get_account(); return BrokerHealth(broker="upstox",healthy=True,authenticated=True,live_trading_enabled=True,message=f"authenticated account={account['broker_account_id']}")
        except Exception as exc:
            return BrokerHealth(broker="upstox",healthy=False,authenticated=False,live_trading_enabled=False,message=str(exc))
