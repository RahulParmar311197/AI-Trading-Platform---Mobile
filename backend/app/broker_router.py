from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, replace, asdict
from datetime import datetime, timezone
from threading import Lock, RLock
from typing import Iterator
import hashlib
import json
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate, normalize_broker_update
from app.broker_snapshot import BrokerSnapshot
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore
from app.trading_gate import TradingGate

@dataclass(frozen=True)
class BrokerRoute:
    name: str
    adapter: BrokerAdapter
    enabled: bool = True
    broker_account_id: int | None = None
    generation: str | None = None

class BrokerRouter:
    def __init__(self,routes:list[BrokerRoute],default_route:str,safety_store:SafetyStateStore|None=None,trading_gate:TradingGate|None=None,max_reconciliation_age_seconds:float=2.0,submission_intent_store:SubmissionIntentStore|None=None):
        if max_reconciliation_age_seconds<=0: raise ValueError("max_reconciliation_age_seconds must be positive")
        self.routes={r.name:r for r in routes}; self.default_route=default_route; self.safety_store=safety_store; self.trading_gate=trading_gate or TradingGate(); self.max_reconciliation_age_seconds=float(max_reconciliation_age_seconds); self.submission_intent_store=submission_intent_store or SubmissionIntentStore(); self._submission_lock=Lock(); self._submission_claims=set(); self._route_lifecycle_lock=RLock()
        if default_route not in self.routes: raise ValueError("default broker route is not configured")
    @contextmanager
    def route_lifecycle_lock(self)->Iterator[None]:
        with self._route_lifecycle_lock: yield
    def get(self,name=None):
        route=self.routes.get(name or self.default_route)
        if route is None or not route.enabled: raise ValueError("broker route unavailable")
        return route
    @staticmethod
    def _request_fingerprint(request:BrokerOrderRequest)->str:
        data=asdict(request); return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")).hexdigest()
    def unresolved_submission_intents(self): return self.submission_intent_store.unresolved()
    def unresolved_submission_intent_count(self)->int: return self.submission_intent_store.unresolved_count()
    def reconcile_unresolved_submission_intents(self,route=None)->list[str]:
        """Resolve persisted intents only from an authoritative broker order snapshot; never resubmit.

        A zero-match authoritative snapshot is intentionally left unresolved because it cannot
        distinguish a genuine no-order result from a broker-side propagation/API race.
        """
        resolved=[]
        with self._route_lifecycle_lock:
            intents=self.submission_intent_store.unresolved(); grouped={}
            for intent in intents: grouped.setdefault(intent.route,[]).append(intent)
            for route_name, route_intents in grouped.items():
                selected=self.get(route_name if route is None else route)
                snapshot_fn=getattr(selected.adapter,"get_order_snapshot",None)
                if snapshot_fn is None: raise RuntimeError("authoritative broker order snapshot is required to recover submission intents")
                try:
                    snapshot=snapshot_fn(); orders=snapshot.require_authoritative()
                except Exception as snapshot_error:
                    if self.safety_store is not None: self.safety_store.halt(f"unresolved submission intent snapshot unavailable: {snapshot_error}")
                    raise RuntimeError("broker order snapshot is not authoritative; trading halted") from snapshot_error
                for intent in route_intents:
                    matches=[dict(o) for o in orders if str(o.get("client_order_id",o.get("tag","")))==intent.client_order_id]
                    if len(matches)>1:
                        if self.safety_store is not None: self.safety_store.halt(f"ambiguous unresolved submission intent: {intent.client_order_id}")
                        raise RuntimeError(f"ambiguous unresolved submission intent: {intent.client_order_id}")
                    if len(matches)==1:
                        match=matches[0]
                        if intent.account_id is not None and (selected.broker_account_id is None or str(intent.account_id)!=str(selected.broker_account_id)):
                            if self.safety_store is not None: self.safety_store.halt(f"submission intent account mismatch: {intent.client_order_id}")
                            raise RuntimeError(f"submission intent account mismatch: {intent.client_order_id}")
                        self.submission_intent_store.resolve(intent.client_order_id); resolved.append(intent.client_order_id); continue
                    # Do not resolve a zero-match intent. The broker snapshot being authoritative
                    # proves the snapshot was complete, not that the submission never happened.
        return resolved
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
    def _recover_after_submit_failure(self,request:BrokerOrderRequest,selected:BrokerRoute,original:Exception)->BrokerOrderUpdate:
        try: existing=self.find_order_by_client_id(request.client_order_id,selected.name)
        except Exception as lookup_error:
            if self.safety_store is not None: self.safety_store.halt(f"ambiguous broker submission for {request.client_order_id}: {lookup_error}")
            raise RuntimeError("broker submission outcome is unknown; trading halted") from lookup_error
        if existing is None: raise original
        if isinstance(existing,dict) and existing.get("multi_order"):
            if self.safety_store is not None: self.safety_store.halt(f"multiple broker orders found for {request.client_order_id}")
            raise RuntimeError("multiple broker orders found; child-order aggregation is required")
        raw={"order_id":str(existing.get("order_id",existing.get("broker_order_id",""))),"status":str(existing.get("status","NEW")),"client_order_id":existing.get("client_order_id",existing.get("tag",request.client_order_id)),"symbol":existing.get("symbol",request.symbol),"side":existing.get("side",request.side),"quantity":existing.get("quantity",request.quantity),"filled_quantity":existing.get("filled_quantity",existing.get("filledQty")),"price":existing.get("price"),"average_price":existing.get("average_price",existing.get("averagePrice")),"message":"BROKER_SUBMISSION_RECOVERED"}
        result=normalize_broker_update(raw,expected=request)
        self.submission_intent_store.resolve(request.client_order_id)
        return result
    def submit(self,request:BrokerOrderRequest,route=None):
        with self._route_lifecycle_lock:
            selected_route=route or request.broker_route or self.default_route; selected=self.get(selected_route); self._require_execution_ready(selected); self._require_account_binding(request,selected); key=(selected_route,str(request.client_order_id))
            with self._submission_lock:
                if key in self._submission_claims:
                    existing=self.find_order_by_client_id(request.client_order_id,selected_route)
                    if existing is not None: raise RuntimeError("submission already in progress for client_order_id")
                    raise RuntimeError("submission already in progress for client_order_id")
                existing=self.find_order_by_client_id(request.client_order_id,selected_route)
                if existing is not None: raise RuntimeError("broker order already exists for client_order_id; use reconciliation path")
                self._submission_claims.add(key)
            try:
                if self.safety_store is not None:
                    state=self.safety_store.load()
                    if state.trading_halted: raise RuntimeError("trading is halted")
                    expected=state.broker_snapshot_fingerprint
                    if expected is None: raise RuntimeError("broker reconciliation fingerprint is unavailable")
                    current=self._current_snapshot_fingerprint(selected)
                    if current!=expected: raise RuntimeError("broker state changed immediately before submission")
                self.submission_intent_store.create(client_order_id=request.client_order_id,route=selected.name,account_id=str(selected.broker_account_id) if selected.broker_account_id is not None else None,symbol=request.symbol,side=request.side,quantity=request.quantity,request_fingerprint=self._request_fingerprint(request))
                try:
                    result=selected.adapter.submit_order(request); self.submission_intent_store.resolve(request.client_order_id); return result
                except Exception as submit_error: return self._recover_after_submit_failure(request,selected,submit_error)
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
            selected=self.get(route)
            try:
                snapshot=selected.adapter.get_order_snapshot(); orders=snapshot.require_authoritative(); matches=[dict(o) for o in orders if str(o.get("client_order_id",o.get("tag","")))==str(client_order_id)]
                if len(matches)>1: raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
                return matches[0] if matches else None
            except NotImplementedError: return selected.adapter.find_order_by_client_id(client_order_id)
    def get_positions(self,route=None):
        with self._route_lifecycle_lock: return self.get(route).adapter.get_positions()
    def get_account(self,route=None):
        with self._route_lifecycle_lock: return self.get(route).adapter.get_account()
    def get_snapshot(self,route=None):
        with self._route_lifecycle_lock:
            selected=self.get(route); fn=getattr(selected.adapter,"get_snapshot",None); snapshot=fn() if fn is not None else BrokerSnapshot(orders=self.get_orders(selected.name),positions=self.get_positions(selected.name))
            if not isinstance(snapshot,BrokerSnapshot): snapshot=BrokerSnapshot(orders=list(snapshot.orders),positions=list(snapshot.positions),fetched_at=float(snapshot.fetched_at))
            return replace(snapshot,broker_route=selected.name,broker_account_id=selected.broker_account_id)
