from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
import inspect
import uuid
from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import PreTradeRiskGate, RiskSnapshot
from app.startup_recovery import StartupRecoveryCoordinator
from app.startup_execution_state import StartupExecutionStateMachine
from app.safety_state import SafetyStateStore
from app.execution_authorization import ExecutionAuthorization
from app.trading_audit import TradingAuditLog

@dataclass(frozen=True)
class ExecutionResult:
    order_id:str; status:str; broker_order_id:str|None=None; message:str|None=None; execution_id:str|None=None

class OrderExecutionService:
    _claim_lock=Lock()
    def __init__(self,router,lifecycle,store,idempotency_store=None,recovery=None,risk_gate=None,risk_snapshot_provider=None,safety_state_store=None,authorization=None,startup_state=None,audit_log=None):
        self.router=router; self.lifecycle=lifecycle; self.store=store; self.idempotency_store=idempotency_store; self.recovery=recovery or StartupRecoveryCoordinator(); self.risk_gate=risk_gate; self.risk_snapshot_provider=risk_snapshot_provider; self.safety_state_store=safety_state_store
        if startup_state is None: raise ValueError("startup_state is required for live execution")
        self.startup_state=startup_state; self.audit_log=audit_log or getattr(startup_state,"audit_log",None) or TradingAuditLog(); self.authorization=authorization or ExecutionAuthorization(safety_state_store or SafetyStateStore(),risk_gate,risk_snapshot_provider,audit_log=self.audit_log)
        if self.risk_gate is not None:self.risk_gate.rebuild_from_lifecycle(self.lifecycle)
    def _audit(self,event_type,execution_id,request=None,**metadata):self.audit_log.record(event_type,metadata={"execution_id":execution_id,"client_order_id":getattr(request,"client_order_id",None),**metadata})
    def _authorize_execution(self,request,execution_id):
        result=self.authorization.check(request);self._audit("EXECUTION_AUTHORIZATION_CORRELATED",execution_id,request,allowed=result.allowed,code=result.code,reason=result.reason)
        if not result.allowed:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message=f"{result.code}: {result.reason or 'execution blocked'}",execution_id=execution_id)
    def _assert_safety_ready(self):
        result=self.authorization.check_safety()
        if not result.allowed:return ExecutionResult("",OrderStatus.REJECTED.value,message=f"{result.code}: {result.reason or 'execution blocked'}")
        if not self.startup_state.execution_allowed:return ExecutionResult("",OrderStatus.REJECTED.value,message=f"STARTUP_EXECUTION_LOCKED: {self.startup_state.state.value}")
    def _recover_broker_order(self,client_order_id):return self.router.find_order_by_client_id(client_order_id)
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
            try:self.risk_gate.update_after_fill(request,filled_quantity,float(self._risk_snapshot(request).position_quantity))
            except Exception:return
    def _create_lifecycle_record(self,request,execution_id):
        if request.client_order_id in self.lifecycle.orders:
            order=self.lifecycle.orders[request.client_order_id]
            if order.execution_id is None:order.execution_id=execution_id
            return
        self.lifecycle.create(request.client_order_id,request.symbol,request.side,request.quantity,execution_id=execution_id,order_type=request.order_type,requested_price=request.price,stop=request.stop,target=request.target,security_id=request.security_id,exchange_segment=request.exchange_segment,product_type=request.product_type,validity=request.validity,trigger_price=request.trigger_price)
    def _save_recovered(self,request,recovered,message,execution_id):
        self._validate_recovered_identity(request,recovered);broker_id=str(recovered.get("order_id",recovered.get("broker_order_id")))
        if broker_id=="None":raise RuntimeError("broker recovery returned an order without broker order id")
        status=self._map_broker_status(str(recovered.get("status","NEW")));filled=float(recovered.get("filled_quantity",recovered.get("filledQty",0)) or 0);average=recovered.get("average_price",recovered.get("averagePrice",recovered.get("price")))
        self._create_lifecycle_record(request,execution_id);order=self.lifecycle.orders[request.client_order_id];order.broker_order_id=broker_id;self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled if status in {OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED} else 0,fill_price=average);self.store.save(self.lifecycle);self._settle_risk_reservation(request,status,filled);self._audit("BROKER_ORDER_RECOVERED",execution_id,request,broker_order_id=broker_id,status=status.value,filled_quantity=filled)
        if self.idempotency_store is not None and status!=OrderStatus.PARTIALLY_FILLED:self.idempotency_store.mark_completed(request.client_order_id)
        return ExecutionResult(request.client_order_id,status.value,broker_id,message,execution_id)
    def submit(self,request):
        execution_id=str(uuid.uuid4());self._audit("EXECUTION_STARTED",execution_id,request);safety_result=self._assert_safety_ready()
        if safety_result is not None:self._audit("EXECUTION_BLOCKED",execution_id,request,reason=safety_result.message);return ExecutionResult(request.client_order_id,safety_result.status,message=safety_result.message,execution_id=execution_id)
        with self._claim_lock:
            safety_result=self._assert_safety_ready()
            if safety_result is not None:self._audit("EXECUTION_BLOCKED",execution_id,request,reason=safety_result.message);return ExecutionResult(request.client_order_id,safety_result.status,message=safety_result.message,execution_id=execution_id)
            authorization_result=self._authorize_execution(request,execution_id)
            if authorization_result is not None:return authorization_result
            existing=self.lifecycle.orders.get(request.client_order_id)
            if existing is not None and existing.status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:return ExecutionResult(request.client_order_id,existing.status.value,existing.broker_order_id,"IDEMPOTENT_REPLAY",execution_id)
            if not self.startup_state.execution_allowed:return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message=f"LIVE_EXECUTION_LOCKED_STARTUP_STATE_{self.startup_state.state.value}",execution_id=execution_id)
            if self.idempotency_store is not None and not self.idempotency_store.claim(request.client_order_id):
                recovered=self._recover_broker_order(request.client_order_id)
                if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED",execution_id)
                return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION",execution_id=execution_id)
            recovered=self._recover_broker_order(request.client_order_id)
            if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED",execution_id)
            self._create_lifecycle_record(request,execution_id);self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMISSION_INTENT);self.store.save(self.lifecycle);self._audit("SUBMISSION_INTENT",execution_id,request)
            try:
                result=self.router.submit(request);self._validate_submission_result(request,result);status=self._map_broker_status(str(result.status));filled=float(result.filled_quantity or 0) if result.filled_quantity is not None else 0.0;average=result.average_price if result.average_price is not None else result.price;self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled,fill_price=average);self.lifecycle.orders[request.client_order_id].broker_order_id=result.order_id;self.store.save(self.lifecycle);self._audit("BROKER_SUBMISSION_RESULT",execution_id,request,broker_order_id=result.order_id,status=status.value,filled_quantity=filled,average_price=average);return ExecutionResult(request.client_order_id,status.value,result.order_id,None,execution_id)
            except Exception as exc:
                self._audit("BROKER_SUBMISSION_ERROR",execution_id,request,error=str(exc));recovered=self._recover_broker_order(request.client_order_id)
                if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED",execution_id)
                self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMITTED);self.store.save(self.lifecycle);return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION",execution_id=execution_id)
