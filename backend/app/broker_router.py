from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_snapshot import BrokerSnapshot
from app.safety_state import SafetyStateStore
from app.trading_gate import TradingGate

@dataclass(frozen=True)
class BrokerRoute:
    name: str
    adapter: BrokerAdapter
    enabled: bool = True

class BrokerRouter:
    def __init__(self, routes: list[BrokerRoute], default_route: str, safety_store: SafetyStateStore | None = None, trading_gate: TradingGate | None = None):
        self.routes={r.name:r for r in routes}; self.default_route=default_route; self.safety_store=safety_store; self.trading_gate=trading_gate or TradingGate(); self._submission_lock=Lock(); self._submission_claims=set()
        if default_route not in self.routes: raise ValueError("default broker route is not configured")
    def get(self,name=None):
        route=self.routes.get(name or self.default_route)
        if route is None or not route.enabled: raise ValueError("broker route unavailable")
        return route
    def _require_execution_ready(self):
        halted=self.safety_store.load().trading_halted if self.safety_store else True; self.trading_gate.require_ready(halted)
    def submit(self,request:BrokerOrderRequest,route=None):
        self._require_execution_ready(); key=(route or self.default_route,str(request.client_order_id))
        with self._submission_lock:
            if key in self._submission_claims:
                existing=self.find_order_by_client_id(request.client_order_id,route)
                if existing is not None: return BrokerOrderUpdate(order_id=str(existing.get("order_id",existing.get("broker_order_id"))),status=str(existing.get("status","NEW")),client_order_id=existing.get("client_order_id"),symbol=existing.get("symbol"),side=existing.get("side"),quantity=existing.get("quantity"),filled_quantity=existing.get("filled_quantity",existing.get("filledQty",0)),price=existing.get("price"),average_price=existing.get("average_price",existing.get("averagePrice")),message="BROKER_CLIENT_ID_REPLAY")
                raise RuntimeError("submission already in progress for client_order_id")
            existing=self.find_order_by_client_id(request.client_order_id,route)
            if existing is not None: return BrokerOrderUpdate(order_id=str(existing.get("order_id",existing.get("broker_order_id"))),status=str(existing.get("status","NEW")),client_order_id=existing.get("client_order_id"),symbol=existing.get("symbol"),side=existing.get("side"),quantity=existing.get("quantity"),filled_quantity=existing.get("filled_quantity",existing.get("filledQty",0)),price=existing.get("price"),average_price=existing.get("average_price",existing.get("averagePrice")),message="BROKER_CLIENT_ID_REPLAY")
            self._submission_claims.add(key)
        try: return self.get(route).adapter.submit_order(request)
        finally:
            with self._submission_lock: self._submission_claims.discard(key)
    def cancel(self,order_id,route=None):
        self._require_execution_ready()
        if not str(order_id).strip(): raise ValueError("order_id is required")
        return self.get(route).adapter.cancel_order(order_id)
    def get_order(self,order_id,route=None): return self.get(route).adapter.get_order(order_id)
    def get_orders(self,route=None):
        get_orders=getattr(self.get(route).adapter,"get_orders",None)
        if get_orders is None: raise NotImplementedError("broker does not support order snapshots")
        return get_orders()
    def find_order_by_client_id(self,client_order_id,route=None):
        adapter=self.get(route); get_orders=getattr(adapter,"get_orders",None)
        if get_orders is not None:
            matches=[dict(order) for order in get_orders() if str(order.get("client_order_id",""))==str(client_order_id)]
            if len(matches)>1: raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
            return matches[0] if matches else None
        return adapter.find_order_by_client_id(client_order_id)
    def get_positions(self,route=None): return self.get(route).adapter.get_positions()
    def get_account(self,route=None): return self.get(route).adapter.get_account()
    def get_snapshot(self,route=None):
        adapter=self.get(route).adapter; get_snapshot=getattr(adapter,"get_snapshot",None)
        return get_snapshot() if get_snapshot is not None else BrokerSnapshot(orders=self.get_orders(route),positions=self.get_positions(route))
