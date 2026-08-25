from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
from time import monotonic
import inspect
import uuid
from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import PreTradeRiskGate, RiskSnapshot
from app.startup_recovery import StartupRecoveryCoordinator
from app.safety_state import SafetyStateStore
from app.execution_authorization import ExecutionAuthorization
from app.trading_audit import TradingAuditLog
from app.execution_observability import ExecutionObservability

@dataclass(frozen=True)
class ExecutionResult:
    order_id:str; status:str; broker_order_id:str|None=None; message:str|None=None; execution_id:str|None=None

class OrderExecutionService:
    _claim_lock=Lock()
    def __init__(self,router,lifecycle,store,idempotency_store=None,recovery=None,risk_gate=None,risk_snapshot_provider=None,safety_state_store=None,authorization=None,startup_state=None,audit_log=None,observability=None):
        self.router=router; self.lifecycle=lifecycle; self.store=store; self.idempotency_store=idempotency_store; self.recovery=recovery or StartupRecoveryCoordinator(); self.risk_gate=risk_gate; self.risk_snapshot_provider=risk_snapshot_provider; self.safety_state_store=safety_state_store; self.observability=observability or ExecutionObservability()
        if startup_state is None: raise ValueError("startup_state is required for live execution")
        self.startup_state=startup_state; self.audit_log=audit_log or getattr(startup_state,"audit_log",None) or TradingAuditLog(); self.authorization=authorization or ExecutionAuthorization(safety_state_store or SafetyStateStore(),risk_gate,risk_snapshot_provider,audit_log=self.audit_log)
        if self.risk_gate is not None:self.risk_gate.rebuild_from_lifecycle(self.lifecycle)
    def _audit(self,event_type,execution_id,request=None,**metadata):self.audit_log.record(event_type,metadata={"execution_id":execution_id,"client_order_id":getattr(request,"client_order_id",None),**metadata})
    def _assert_safety_ready(self):
        result=self.authorization.check_safety()
        if not result.allowed:return ExecutionResult("",OrderStatus.REJECTED.value,message=f"{result.code}: {result.reason or 'execution blocked'}")
        if not self.startup_state.execution_allowed:return ExecutionResult("",OrderStatus.REJECTED.value,message=f"STARTUP_EXECUTION_LOCKED: {self.startup_state.status.reason or self.startup_state.state.value}")
    @staticmethod
    def _validate_recovered_identity(request,recovered):
        for key,expected in (("client_order_id",request.client_order_id),("symbol",request.symbol),("side",request.side)):
            value=recovered.get(key)
            if value is not None and str(value).upper()!=str(expected).upper():raise RuntimeError(f"broker recovery returned an order for a different {key}")
        quantity=recovered.get("quantity",recovered.get("requested_quantity"))
        if quantity is not None and abs(float(quantity)-float(request.quantity))>1e-9:raise RuntimeError("broker recovery returned an order with a different requested quantity")
    @staticmethod
    def _validate_submission_result(request,result):
        broker_id=getattr(result,"order_id",None)
        if broker_id is None or not str(broker_id).strip():raise RuntimeError("broker submission returned no broker order id")
        for key,expected in (("client_order_id",request.client_order_id),("symbol",request.symbol),("side",request.side)):
            value=getattr(result,key,None)
            if value is not None and str(value).upper()!=str(expected).upper():raise RuntimeError(f"broker submission returned a different {key}")
    def _map_broker_status(self,status):
        n=status.upper().strip()
        if n in {"FILLED","TRADED","COMPLETE"}:return OrderStatus.FILLED
        if n in {"PARTIALLY_FILLED","PART_TRADED","PARTIALLY_TRADED"}:return OrderStatus.PARTIALLY_FILLED
        if n in {"CANCELLED","CANCELED"}:return OrderStatus.CANCELLED
        if n in {"REJECTED","FAILED","ERROR"}:return OrderStatus.REJECTED
        return OrderStatus.SUBMITTED
    def _risk_snapshot(self,request):
        if self.risk_snapshot_provider is None:raise RuntimeError("risk snapshot provider unavailable")
        try:
            signature=inspect.signature(self.risk_snapshot_provider)
            try:signature.bind(request);return self.risk_snapshot_provider(request)
            except TypeError:signature.bind();return self.risk_snapshot_provider()
        except (TypeError,ValueError):return self.risk_snapshot_provider(request)
    def _settle_risk_reservation(self,request,status,filled_quantity=0.0):
        if self.risk_gate is None:return
        if status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:self.risk_gate.release(request.client_order_id)
        elif status==OrderStatus.PARTIALLY_FILLED:
            decision=self.risk_gate.update_after_fill(request,filled_quantity,float(self._risk_snapshot(request).position_quantity))
            if not decision.allowed:raise RuntimeError(decision.reason)
    def _finalize_idempotency(self,request,status):
        if self.idempotency_store is None:return
        if status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:self.idempotency_store.mark_completed(request.client_order_id)
    def _create_lifecycle_record(self,request,execution_id):
        if request.client_order_id in self.lifecycle.orders:
            order=self.lifecycle.orders[request.client_order_id]
            if order.execution_id is None:order.execution_id=execution_id
            if order.owner_user_id is None and request.owner_user_id is not None:order.owner_user_id=int(request.owner_user_id)
            elif request.owner_user_id is not None and order.owner_user_id != int(request.owner_user_id):raise RuntimeError("execution owner mismatch for existing lifecycle order")
            if order.broker_account_id is None and request.broker_account_id is not None:order.broker_account_id=int(request.broker_account_id)
            elif request.broker_account_id is not None and order.broker_account_id != int(request.broker_account_id):raise RuntimeError("broker account mismatch for existing lifecycle order")
            if order.broker_route is None and request.broker_route is not None:order.broker_route=str(request.broker_route)
            elif request.broker_route is not None and order.broker_route != str(request.broker_route):raise RuntimeError("broker route mismatch for existing lifecycle order")
            return
        self.lifecycle.create(request.client_order_id,request.symbol,request.side,request.quantity,execution_id=execution_id,owner_user_id=request.owner_user_id,broker_account_id=request.broker_account_id,broker_route=request.broker_route,order_type=request.order_type,requested_price=request.price,stop=request.stop,target=request.target,security_id=request.security_id,exchange_segment=request.exchange_segment,product_type=request.product_type,validity=request.validity,trigger_price=request.trigger_price)
    def _save_recovered(self,request,recovered,message,execution_id):
        self._validate_recovered_identity(request,recovered);broker_id=str(recovered.get("order_id",recovered.get("broker_order_id")))
        if broker_id=="None":raise RuntimeError("broker recovery returned an order without broker order id")
        status=self._map_broker_status(str(recovered.get("status","NEW")));filled=float(recovered.get("filled_quantity",recovered.get("filledQty",0)) or 0);average=recovered.get("average_price",recovered.get("averagePrice",recovered.get("price")))
        self._create_lifecycle_record(request,execution_id);order=self.lifecycle.orders[request.client_order_id];order.broker_order_id=broker_id;self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled if status in {OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED} else 0,fill_price=average);self.store.save(self.lifecycle);self._settle_risk_reservation(request,status,filled);self._audit("BROKER_ORDER_RECOVERED",execution_id,request,broker_order_id=broker_id,status=status.value,filled_quantity=filled);self._finalize_idempotency(request,status)
        return ExecutionResult(request.client_order_id,status.value,broker_id,message,execution_id)
    def _reconcile_ambiguous_submission(self,request,execution_id,original_error):
        self._audit("BROKER_SUBMISSION_AMBIGUOUS",execution_id,request,error=str(original_error));started=monotonic()
        try:recovered=self.router.find_order_by_client_id(request.client_order_id,request.broker_route)
        except Exception as recovery_error:self.observability.observe_latency("recovery_latency",(monotonic()-started)*1000);self._audit("BROKER_RECOVERY_ERROR",execution_id,request,error=str(recovery_error));return None
        self.observability.observe_latency("recovery_latency",(monotonic()-started)*1000)
        if recovered is not None:
            self.observability.increment("recovery_found")
            self.observability.increment("duplicate_preventions")
            try:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED_AFTER_AMBIGUOUS_SUBMISSION",execution_id)
            except Exception as recovery_error:self._audit("BROKER_RECOVERY_ERROR",execution_id,request,error=str(recovery_error));return None
        self.observability.increment("recovery_safe_retries")
        self._audit("BROKER_SUBMISSION_UNRESOLVED",execution_id,request,reason="no broker order found after ambiguous submission");return None
    def _release_reservation(self,request,execution_id,reason):
        if self.risk_gate is not None:self.risk_gate.release(request.client_order_id);self._audit("RISK_EXPOSURE_RELEASED",execution_id,request,reason=reason)
    def submit(self,request):
        self.observability.increment("submissions")
        execution_id=str(uuid.uuid4());self._audit("EXECUTION_STARTED",execution_id,request);safety_result=self._assert_safety_ready()
        if safety_result is not None:self._audit("EXECUTION_BLOCKED",execution_id,request,reason=safety_result.message);return ExecutionResult(request.client_order_id,safety_result.status,message=safety_result.message,execution_id=execution_id)
        if not request.broker_account_id or not request.broker_route:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="BROKER_ACCOUNT_BINDING_REQUIRED",execution_id=execution_id)
        with self._claim_lock:
            authorization_result=self.authorization.check(request);self._audit("EXECUTION_AUTHORIZATION_CORRELATED",execution_id,request,allowed=authorization_result.allowed,code=authorization_result.code,reason=authorization_result.reason)
            if not authorization_result.allowed:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message=f"{authorization_result.code}: {authorization_result.reason or 'execution blocked'}",execution_id=execution_id)
            reservation_acquired=False
            if self.risk_gate is not None:
                snapshot=authorization_result.risk_snapshot
                if snapshot is None:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="RISK_SNAPSHOT_UNAVAILABLE: authorized execution has no risk snapshot",execution_id=execution_id)
                reservation=self.risk_gate.reserve(request,snapshot)
                if not reservation.allowed:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message=reservation.reason,execution_id=execution_id)
                reservation_acquired=True;self._audit("RISK_EXPOSURE_RESERVED",execution_id,request,signed_quantity=self.risk_gate.reservations.get(request.client_order_id))
            existing=self.lifecycle.orders.get(request.client_order_id)
            if existing is not None and existing.status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:
                self.observability.increment("duplicate_preventions")
                if reservation_acquired:self._release_reservation(request,execution_id,"IDEMPOTENT_REPLAY")
                return ExecutionResult(request.client_order_id,existing.status.value,existing.broker_order_id,"IDEMPOTENT_REPLAY",execution_id)
            if not self.startup_state.execution_allowed:
                if reservation_acquired:self._release_reservation(request,execution_id,"STARTUP_EXECUTION_LOCKED")
                return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message=f"LIVE_EXECUTION_LOCKED_STARTUP_STATE_{self.startup_state.state.value}",execution_id=execution_id)
            if self.idempotency_store is not None and not self.idempotency_store.claim(request.client_order_id,execution_id):
                started=monotonic()
                try:recovered=self.router.find_order_by_client_id(request.client_order_id,request.broker_route)
                except Exception as recovery_error:
                    self.observability.observe_latency("recovery_latency",(monotonic()-started)*1000)
                    if reservation_acquired:self._release_reservation(request,execution_id,"IDEMPOTENCY_CLAIM_RECOVERY_ERROR")
                    return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION_RECOVERY_ERROR",execution_id=execution_id)
                self.observability.observe_latency("recovery_latency",(monotonic()-started)*1000)
                if recovered is not None:
                    self.observability.increment("recovery_found");self.observability.increment("duplicate_preventions")
                    try:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED_FROM_PERSISTED_CLAIM",execution_id)
                    except Exception:
                        if reservation_acquired:self._release_reservation(request,execution_id,"PERSISTED_CLAIM_RECOVERY_ERROR")
                        return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION_RECOVERY_ERROR",execution_id=execution_id)
                self.observability.increment("recovery_safe_retries")
                if reservation_acquired:self._release_reservation(request,execution_id,"EXECUTION_CLAIMED_BY_OTHER")
                return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION_CLAIMED_BY_OTHER",execution_id=execution_id)
            try:
                started=monotonic();recovered=self.router.find_order_by_client_id(request.client_order_id,request.broker_route);self.observability.observe_latency("recovery_latency",(monotonic()-started)*1000)
                if recovered is not None:
                    self.observability.increment("recovery_found");self.observability.increment("duplicate_preventions")
                    return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED",execution_id)
                self._create_lifecycle_record(request,execution_id);self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMISSION_INTENT);self.store.save(self.lifecycle);self._audit("SUBMISSION_INTENT",execution_id,request)
            except Exception:
                if reservation_acquired:self._release_reservation(request,execution_id,"PRE_SUBMISSION_FAILURE")
                return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION_PRE_SUBMISSION_FAILURE",execution_id=execution_id)
            started=monotonic()
            try:
                result=self.router.submit(request,request.broker_route);self.observability.observe_latency("broker_latency",(monotonic()-started)*1000);self._validate_submission_result(request,result);status=self._map_broker_status(str(result.status));filled=float(result.filled_quantity or 0) if result.filled_quantity is not None else 0.0;average=result.average_price if result.average_price is not None else result.price;self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled,fill_price=average);self.lifecycle.orders[request.client_order_id].broker_order_id=result.order_id;self.store.save(self.lifecycle);self._settle_risk_reservation(request,status,filled);self._finalize_idempotency(request,status);self.observability.increment("submitted");self._audit("BROKER_SUBMISSION_RESULT",execution_id,request,broker_order_id=result.order_id,status=status.value,filled_quantity=filled,average_price=average);return ExecutionResult(request.client_order_id,status.value,result.order_id,None,execution_id)
            except Exception as exc:
                self.observability.observe_latency("broker_latency",(monotonic()-started)*1000);self.observability.increment("broker_failures")
                recovered_result=self._reconcile_ambiguous_submission(request,execution_id,exc)
                if recovered_result is not None:return recovered_result
                self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMITTED);self.store.save(self.lifecycle);return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION_NO_RETRY",execution_id=execution_id)
