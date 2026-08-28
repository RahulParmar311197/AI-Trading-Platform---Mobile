from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock, RLock
from typing import Iterator
import hashlib
import json
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate, normalize_broker_update
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation import ReconciliationEngine
from app.reconciliation_coordinator import ReconciliationCoordinator
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
    def __init__(self,routes:list[BrokerRoute],default_route:str,safety_store:SafetyStateStore|None=None,trading_gate:TradingGate|None=None,max_reconciliation_age_seconds:float=2.0,submission_intent_store:SubmissionIntentStore|None=None,reconciliation_engine:ReconciliationEngine|None=None,context_attestor:BrokerContextAttestor|None=None):
        if max_reconciliation_age_seconds<=0: raise ValueError("max_reconciliation_age_seconds must be positive")
        if context_attestor is not None and not isinstance(context_attestor, BrokerContextAttestor): raise ValueError("context attestor is invalid")
        self.routes={r.name:r for r in routes}; self.default_route=default_route; self.safety_store=safety_store; self.trading_gate=trading_gate or TradingGate(); self.max_reconciliation_age_seconds=float(max_reconciliation_age_seconds); self.submission_intent_store=submission_intent_store or SubmissionIntentStore(); self.reconciliation_engine=reconciliation_engine or ReconciliationEngine(self.submission_intent_store); self.context_attestor=context_attestor; self._submission_lock=Lock(); self._submission_claims=set(); self._route_lifecycle_lock=RLock()
        if default_route not in self.routes: raise ValueError("default broker route is not configured")
        if self.reconciliation_engine.submission_intent_store is not self.submission_intent_store:
            raise ValueError("reconciliation engine must use the router submission intent store")
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
    def _halt_if_unresolved_submission_intents(self)->None:
        count=self.submission_intent_store.unresolved_count()
        if count:
            if self.safety_store is not None: self.safety_store.halt(f"{count} unresolved submission intent(s) remain")
            raise RuntimeError("unresolved submission intents remain; trading halted")
    def reconcile_unresolved_submission_intents(self,route=None)->list[str]:
        resolved=[]
        with self._route_lifecycle_lock:
            intents=self.submission_intent_store.unresolved(); grouped={}
            for intent in intents: grouped.setdefault(intent.route,[]).append(intent)
            for route_name, route_intents in grouped.items():
                selected=self.get(route_name if route is None else route)
                snapshot_fn=getattr(selected.adapter,"get_order_snapshot",None)
                if snapshot_fn is None: raise RuntimeError("authoritative broker order snapshot is required to recover submission intents")
                try: snapshot=snapshot_fn(); orders=snapshot.require_authoritative()
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
            if self.submission_intent_store.unresolved_count():
                if self.safety_store is not None: self.safety_store.halt("unresolved submission intents remain after broker reconciliation")
        return resolved
    def _verify_route_identity(self,route:BrokerRoute)->None:
        verifier=getattr(route.adapter,"verify_authenticated_identity",None)
        if verifier is None:
            return
        try:
            verifier()
        except Exception as exc:
            if self.safety_store is not None:
                self.safety_store.halt(f"broker identity verification failed for route {route.name}")
            raise RuntimeError("broker authenticated identity could not be verified; trading halted") from exc
    def _authoritative_reconciliation_snapshot(self,route:BrokerRoute)->BrokerSnapshot:
        self._verify_route_identity(route)
        order_snapshot_fn=getattr(route.adapter,"get_order_snapshot",None); position_snapshot_fn=getattr(route.adapter,"get_position_snapshot",None)
        if order_snapshot_fn is None: raise RuntimeError("authoritative broker order snapshot is required for reconciliation")
        if position_snapshot_fn is None: raise RuntimeError("authoritative broker position snapshot is required for reconciliation")
        orders=order_snapshot_fn().require_authoritative(); positions=position_snapshot_fn().require_authoritative()
        return BrokerSnapshot(orders=[dict(x) for x in orders],positions=[dict(x) for x in positions],broker_route=route.name,broker_account_id=route.broker_account_id)
    def _current_snapshot_fingerprint(self,route:BrokerRoute)->str: return self._authoritative_reconciliation_snapshot(route).fingerprint()
    def reconcile_authoritative(self,internal_orders:list[dict],internal_positions:list[dict],route=None,broker_ready:bool=True):
        """Run the production reconciliation path from one authoritative broker snapshot."""
        selected=self.get(route)
        if self.context_attestor is None: raise RuntimeError("canonical broker context attestor is required for verified reconciliation")
        if selected.broker_account_id is None: raise RuntimeError("broker route must be bound to a broker account for verified reconciliation")
        if selected.generation is None: raise RuntimeError("broker route generation is required for verified reconciliation")
        snapshot=self._authoritative_reconciliation_snapshot(selected)
        coordinator=ReconciliationCoordinator(engine=self.reconciliation_engine,route=selected.name,account_id=str(selected.broker_account_id),route_generation=str(selected.generation),context_attestor=self.context_attestor,generation=0)
        return coordinator.reconcile(internal_orders=internal_orders,internal_positions=internal_positions,broker_snapshot=snapshot,broker_ready=broker_ready)
    def _reconciliation_record(self,route:BrokerRoute):
        if self.safety_store is None:
            return None
        state=self.safety_store.load()
        if route.broker_account_id is not None:
            record=self.safety_store.account_reconciliation(str(route.broker_account_id))
            if record is None:
                raise RuntimeError("broker account has not been reconciled")
            return record
        return {
            "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
            "reconciliation_generation": state.reconciliation_generation,
            "broker_snapshot_fingerprint": state.broker_snapshot_fingerprint,
            "route_generation": None,
        }
    def _require_execution_ready(self,route:BrokerRoute)->None:
        self._halt_if_unresolved_submission_intents()
        if self.safety_store is None: halted=True; state=None
        else: state=self.safety_store.load(); halted=state.trading_halted
        self.trading_gate.require_ready(halted)
        if halted or state is None: return
        record=self._reconciliation_record(route)
        if route.generation is not None:
            route_generation=record.get("route_generation") if record else None
            if route_generation is None or str(route_generation)!=str(route.generation): raise RuntimeError("broker route generation is not reconciled")
        reconciled_at_raw=record.get("last_reconciliation_at") if record else None
        if not reconciled_at_raw: raise RuntimeError("broker reconciliation timestamp is unavailable")
        reconciled_at=datetime.fromisoformat(str(reconciled_at_raw))
        if reconciled_at.tzinfo is None: raise RuntimeError("broker reconciliation timestamp is unavailable")
        age=(datetime.now(timezone.utc)-reconciled_at.astimezone(timezone.utc)).total_seconds()
        if age<0 or age>self.max_reconciliation_age_seconds: raise RuntimeError("broker reconciliation is stale")
        expected=record.get("broker_snapshot_fingerprint") if record else None
        if not expected: raise RuntimeError("broker reconciliation fingerprint is unavailable")
        current=self._current_snapshot_fingerprint(route)
        if current!=expected: raise RuntimeError("broker state changed since reconciliation")
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
        actual_client_id=existing.get("client_order_id") or existing.get("tag")
        actual_symbol=existing.get("symbol")
        actual_side=existing.get("side")
        actual_quantity=existing.get("quantity",existing.get("order_quantity",existing.get("requested_quantity")))
        if not actual_client_id or not actual_symbol or not actual_side or actual_quantity in (None, ""):
            if self.safety_store is not None: self.safety_store.halt(f"incomplete broker recovery payload for {request.client_order_id}")
            raise RuntimeError("broker submission outcome is unknown; recovery payload is incomplete")
        raw={"order_id":str(existing.get("order_id",existing.get("broker_order_id",""))),"status":str(existing.get("status","")),"client_order_id":actual_client_id,"symbol":actual_symbol,"side":actual_side,"quantity":actual_quantity,"filled_quantity":existing.get("filled_quantity",existing.get("filledQty",existing.get("filled_qty"))),"price":existing.get("price"),"average_price":existing.get("average_price",existing.get("averagePrice")),"message":"BROKER_SUBMISSION_RECOVERED"}
        result=normalize_broker_update(raw,expected=request); self.submission_intent_store.resolve(request.client_order_id); return result
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
                    record=self._reconciliation_record(selected)
                    expected=record.get("broker_snapshot_fingerprint") if record else None
                    if expected is None: raise RuntimeError("broker reconciliation fingerprint is unavailable")
                    current=self._current_snapshot_fingerprint(selected)
                    if current!=expected: raise RuntimeError("broker state changed immediately before submission")
                self.submission_intent_store.create(client_order_id=request.client_order_id,route=selected.name,account_id=str(selected.broker_account_id) if selected.broker_account_id is not None else None,symbol=request.symbol,side=request.side,quantity=request.quantity,request_fingerprint=self._request_fingerprint(request))
                try: result=selected.adapter.submit_order(request); self.submission_intent_store.resolve(request.client_order_id); return result
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
    def get_snapshot(self,route=None): return self._authoritative_reconciliation_snapshot(self.get(route))
