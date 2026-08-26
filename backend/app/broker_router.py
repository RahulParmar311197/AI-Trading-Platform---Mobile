from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import Lock, RLock
from typing import Iterator
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_snapshot import BrokerSnapshot
from app.safety_state import SafetyStateStore
from app.trading_gate import TradingGate

@dataclass(frozen=True)
class BrokerRoute:
    name: str
    adapter: BrokerAdapter
    enabled: bool = True
    broker_account_id: int | None = None
    generation: str | None = None

class BrokerRouter:
    def __init__(self,routes:list[BrokerRoute],default_route:str,safety_store:SafetyStateStore|None=None,trading_gate:TradingGate|None=None,max_reconciliation_age_seconds:float=2.0):
        if max_reconciliation_age_seconds<=0: raise ValueError("max_reconciliation_age_seconds must be positive")
        self.routes={r.name:r for r in routes}; self.default_route=default_route; self.safety_store=safety_store; self.trading_gate=trading_gate or TradingGate(); self.max_reconciliation_age_seconds=float(max_reconciliation_age_seconds); self._submission_lock=Lock(); self._submission_claims=set(); self._route_lifecycle_lock=RLock()
        if default_route not in self.routes: raise ValueError("default broker route is not configured")
    @contextmanager
    def route_lifecycle_lock(self)->Iterator[None]:
        with self._route_lifecycle_lock: yield
    def get(self,name=None):
        route=self.routes.get(name or self.default_route)
        if route is None or not route.enabled: raise ValueError("broker route unavailable")
        return route
    def _current_snapshot_fingerprint(self,route:BrokerRoute)->str:
        get_snapshot=getattr(route.adapter,"get_snapshot",None)
        if get_snapshot is not None:
            snapshot=get_snapshot()
            if not isinstance(snapshot,BrokerSnapshot): raise RuntimeError("broker snapshot is invalid")
            return replace(snapshot,broker_route=route.name,broker_account_id=route.broker_account_id).fingerprint()
        get_orders=getattr(route.adapter,"get_orders",None)
        if get_orders is None: raise RuntimeError("broker order snapshot is unavailable")
        orders=get_orders(); positions=route.adapter.get_positions()
        if not isinstance(orders,list) or not isinstance(positions,list): raise RuntimeError("broker snapshot is unavailable")
        return BrokerSnapshot(orders=[dict(x) for x in orders],positions=[dict(x) for x in positions],broker_route=route.name,broker_account_id=route.broker_account_id).fingerprint()
    def _require_execution_ready(self,route:BrokerRoute)->None:
        if self.safety_store is None: halted=True; state=None
        else: state=self.safety_store.load(); halted=state.trading_halted
        self.trading_gate.require_ready(halted)
        if halted or state is None: return
        if route.generation is not None:
            if state.reconciliation_generation is None: raise RuntimeError("broker route has not been reconciled")
            if str(state.reconciliation_generation)!=str(route.generation): raise RuntimeError("broker route generation is not reconciled")
        if route.broker_account_id is not None:
            if state.reconciliation_account_id is None: raise RuntimeError("broker account has not been reconciled")
            if str(state.reconciliation_account_id)!=str(route.broker_account_id): raise RuntimeError("broker account is not reconciled")
        reconciled_at=state.last_reconciliation_at
        if reconciled_at is None or reconciled_at.tzinfo is None: raise RuntimeError("broker reconciliation timestamp is unavailable")
        age=(datetime.now(timezone.utc)-reconciled_at.astimezone(timezone.utc)).total_seconds()
        if age<0 or age>self.max_reconciliation_age_seconds: raise RuntimeError("broker reconciliation is stale")
        if not state.broker_snapshot_fingerprint: raise RuntimeError("broker reconciliation fingerprint is unavailable")
        current=self._current_snapshot_fingerprint(route)
        if current!=state.broker_snapshot_fingerprint: raise RuntimeError("broker state changed since reconciliation")
    def _require_account_binding(self,request:BrokerOrderRequest,route:BrokerRoute)->None:
        if request.broker_account_id is None: return
        if route.broker_account_id is None: raise RuntimeError("broker route is not bound to a broker account")
        if int(route.broker_account_id)!=int(request.broker_account_id): raise RuntimeError("broker account does not match broker route")
        if request.broker_route_generation is None: raise RuntimeError("broker account route generation is required")
        if route.generation is None or str(route.generation)!=str(request.broker_route_generation): raise RuntimeError("broker account route generation is stale")
    def submit(self,request:BrokerOrderRequest,route=None):
        with self._route_lifecycle_lock:
            selected_route=route or request.broker_route or self.default_route; selected=self.get(selected_route); self._require_execution_ready(selected); self._require_account_binding(request,selected); key=(selected_route,str(request.client_order_id))
            with self._submission_lock:
                if key in self._submission_claims:
                    existing=self.find_order_by_client_id(request.client_order_id,selected_route)
                    if existing is not None: return BrokerOrderUpdate(order_id=str(existing.get("order_id",existing.get("broker_order_id"))),status=str(existing.get("status","NEW")),client_order_id=existing.get("client_order_id"),symbol=existing.get("symbol"),side=existing.get("side"),quantity=existing.get("quantity"),filled_quantity=existing.get("filled_quantity",existing.get("filledQty",0)),price=existing.get("price"),average_price=existing.get("average_price",existing.get("averagePrice")),message="BROKER_CLIENT_ID_REPLAY")
                    raise RuntimeError("submission already in progress for client_order_id")
                existing=self.find_order_by_client_id(request.client_order_id,selected_route)
                if existing is not None: return BrokerOrderUpdate(order_id=str(existing.get("order_id",existing.get("broker_order_id"))),status=str(existing.get("status","NEW")),client_order_id=existing.get("client_order_id"),symbol=existing.get("symbol"),side=existing.get("side"),quantity=existing.get("quantity"),filled_quantity=existing.get("filled_quantity",existing.get("filledQty",0)),price=existing.get("price"),average_price=existing.get("average_price",existing.get("averagePrice")),message="BROKER_CLIENT_ID_REPLAY")
                self._submission_claims.add(key)
            try: return selected.adapter.submit_order(request)
            finally:
                with self._submission_lock: self._submission_claims.discard(key)
    def cancel(self,order_id,route=None):
        with self._route_lifecycle_lock:
            if not str(order_id).strip(): raise ValueError("order_id is required")
            return self.get(route).adapter.cancel_order(order_id)
    def get_order(self,order_id,route=None):
        with self._route_lifecycle_lock: return self.get(route).adapter.get_order(order_id)
    def get_orders(self,route=None):
        with self._route_lifecycle_lock:
            fn=getattr(self.get(route).adapter,"get_orders",None)
            if fn is None: raise NotImplementedError("broker does not support order snapshots")
            return fn()
    def find_order_by_client_id(self,client_order_id,route=None):
        with self._route_lifecycle_lock:
            selected=self.get(route); fn=getattr(selected.adapter,"get_orders",None)
            if fn is not None:
                matches=[dict(o) for o in fn() if str(o.get("client_order_id",""))==str(client_order_id)]
                if len(matches)>1: raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
                return matches[0] if matches else None
            return selected.adapter.find_order_by_client_id(client_order_id)
    def get_positions(self,route=None):
        with self._route_lifecycle_lock: return self.get(route).adapter.get_positions()
    def get_account(self,route=None):
        with self._route_lifecycle_lock: return self.get(route).adapter.get_account()
    def get_snapshot(self,route=None):
        with self._route_lifecycle_lock:
            selected=self.get(route); fn=getattr(selected.adapter,"get_snapshot",None); snapshot=fn() if fn is not None else BrokerSnapshot(orders=self.get_orders(selected.name),positions=self.get_positions(selected.name))
            if not isinstance(snapshot,BrokerSnapshot): snapshot=BrokerSnapshot(orders=list(snapshot.orders),positions=list(snapshot.positions),fetched_at=float(snapshot.fetched_at))
            return replace(snapshot,broker_route=selected.name,broker_account_id=selected.broker_account_id)
