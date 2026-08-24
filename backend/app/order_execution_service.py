from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
import inspect
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

@dataclass(frozen=True)
class ExecutionResult:
    order_id:str; status:str; broker_order_id:str|None=None; message:str|None=None

class OrderExecutionService:
    _claim_lock=Lock()
    def __init__(self,router,lifecycle,store,idempotency_store=None,recovery=None,risk_gate=None,risk_snapshot_provider=None,safety_state_store=None,authorization=None,startup_state=None):
        self.router=router; self.lifecycle=lifecycle; self.store=store; self.idempotency_store=idempotency_store; self.recovery=recovery or StartupRecoveryCoordinator(); self.risk_gate=risk_gate; self.risk_snapshot_provider=risk_snapshot_provider; self.safety_state_store=safety_state_store
        if startup_state is None: raise ValueError("startup_state is required for live execution")
        self.startup_state: StartupExecutionStateMachine = startup_state
        self.authorization=authorization or ExecutionAuthorization(safety_state_store or SafetyStateStore(), risk_gate, risk_snapshot_provider)
        if self.risk_gate is not None:self.risk_gate.rebuild_from_lifecycle(self.lifecycle)
    def _authorize_execution(self, request):
        result = self.authorization.check(request)
        if not result.allowed:
            return ExecutionResult(request.client_order_id, OrderStatus.REJECTED.value, message=f"{result.code}: {result.reason or 'execution blocked'}")
        return None
    def _assert_safety_ready(self):
        result=self.authorization.check_safety()
        if not result.allowed:return ExecutionResult("",OrderStatus.REJECTED.value,message=f"{result.code}: {result.reason or 'execution blocked'}")
        if not self.startup_state.execution_allowed:
            return ExecutionResult("",OrderStatus.REJECTED.value,message=f"STARTUP_EXECUTION_LOCKED: {self.startup_state.state.value}")
        return None
    def _recover_broker_order(self,client_order_id): return self.router.find_order_by_client_id(client_order_id)
    @staticmethod
    def _validate_recovered_identity(request,recovered):
        for key,expected in (("client_order_id",request.client_order_id),("symbol",request.symbol),("side",request.side)):
            value=recovered.get(key)
            if value is not None and str(value).upper()!=str(expected).upper(): raise RuntimeError(f"broker recovery returned an order for a different {key}")
        quantity=recovered.get("quantity",recovered.get("requested_quantity"))
        if quantity is not None and abs(float(quantity)-float(request.quantity))>1e-9:raise RuntimeError("broker recovery returned an order with a different requested quantity")
    @staticmethod
    def _validate_submission_result(request,result):
        broker_id=getattr(result,"order_id",None)
        if broker_id is None or not str(broker_id).strip():raise RuntimeError("broker submission returned no broker order id")
        for key,expected in (("client_order_id",request.client_order_id),("symbol",request.symbol),("side",request.side)):
            value=getattr(result,key,None)
            if value is not None and str(value).upper()!=str(expected).upper():raise RuntimeError(f"broker submission returned a different {key}")
        quantity=getattr(result,"quantity",None)
        if quantity is not None:
            try:
                if abs(float(quantity)-float(request.quantity))>1e-9:raise RuntimeError("broker submission returned a different requested quantity")
            except (TypeError,ValueError):raise RuntimeError("broker submission returned an invalid requested quantity")
        status=str(getattr(result,"status","")).upper().strip(); filled=getattr(result,"filled_quantity",None); average=getattr(result,"average_price",None)
        if filled is not None:
            try:filled_value=float(filled)
            except (TypeError,ValueError):raise RuntimeError("broker submission returned an invalid filled quantity")
            if filled_value < 0 or filled_value > float(request.quantity)+1e-9:raise RuntimeError("broker submission returned an invalid filled quantity")
            if status in {"FILLED","TRADED","COMPLETE"} and abs(filled_value-float(request.quantity))>1e-9:raise RuntimeError("broker reported FILLED with incomplete quantity")
            if filled_value > 0:
                if average is None: raise RuntimeError("broker submission returned a fill without an average price")
                try:average_value=float(average)
                except (TypeError,ValueError):raise RuntimeError("broker submission returned an invalid average price")
                if average_value <= 0:raise RuntimeError("broker submission returned a non-positive average price")
        elif status in {"FILLED","TRADED","COMPLETE"}:raise RuntimeError("broker reported FILLED without filled quantity")
    def _map_broker_status(self,status):
        n=status.upper().strip()
        if n in {"FILLED","TRADED","COMPLETE"}:return OrderStatus.FILLED
        if n in {"PARTIALLY_FILLED","PART_TRADED","PARTIALLY_TRADED"}:return OrderStatus.PARTIALLY_FILLED
        if n in {"CANCELLED","CANCELED"}:return OrderStatus.CANCELLED
        if n in {"REJECTED","FAILED","ERROR"}:return OrderStatus.REJECTED
        return OrderStatus.SUBMITTED
    def _risk_snapshot(self,request):
        if self.risk_snapshot_provider is None:raise RuntimeError("risk snapshot provider unavailable")
        provider=self.risk_snapshot_provider
        try:
            signature=inspect.signature(provider)
            try:signature.bind(request);return provider(request)
            except TypeError:signature.bind();return provider()
        except (TypeError,ValueError):return provider(request)
    def _settle_risk_reservation(self,request,status,filled_quantity=0.0):
        if self.risk_gate is None:return
        if status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:self.risk_gate.release(request.client_order_id)
        elif status==OrderStatus.PARTIALLY_FILLED:
            try:self.risk_gate.update_after_fill(request,filled_quantity,float(self._risk_snapshot(request).position_quantity))
            except Exception:return
    def _create_lifecycle_record(self,request):
        if request.client_order_id in self.lifecycle.orders:return
        self.lifecycle.create(request.client_order_id,request.symbol,request.side,request.quantity,order_type=request.order_type,requested_price=request.price,stop=request.stop,target=request.target,security_id=request.security_id,exchange_segment=request.exchange_segment,product_type=request.product_type,validity=request.validity,trigger_price=request.trigger_price)
    def _save_recovered(self,request,recovered,message):
        self._validate_recovered_identity(request,recovered);broker_id=str(recovered.get("order_id",recovered.get("broker_order_id")))
        if broker_id=="None":raise RuntimeError("broker recovery returned an order without broker order id")
        status=self._map_broker_status(str(recovered.get("status","NEW")));filled=float(recovered.get("filled_quantity",recovered.get("filledQty",0)) or 0);average=recovered.get("average_price",recovered.get("averagePrice",recovered.get("price")))
        if filled<0 or filled>request.quantity+1e-9:raise RuntimeError("invalid recovered filled quantity")
        if filled>0 and average is None:raise RuntimeError("broker recovery returned a fill without an average price")
        self._create_lifecycle_record(request);order=self.lifecycle.orders[request.client_order_id];order.broker_order_id=broker_id;self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled if status in {OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED} else 0,fill_price=average);self.store.save(self.lifecycle);self._settle_risk_reservation(request,status,filled)
        if self.idempotency_store is not None and status!=OrderStatus.PARTIALLY_FILLED:self.idempotency_store.mark_completed(request.client_order_id)
        return ExecutionResult(request.client_order_id,status.value,broker_id,message)
    def _authorize_risk(self,request):
        if self.risk_gate is None:return None
        if self.risk_snapshot_provider is None:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="RISK_SNAPSHOT_UNAVAILABLE")
        try:
            initial=self._risk_snapshot(request);decision=self.risk_gate.reserve(request,initial)
            if not decision.allowed:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message=decision.reason)
            fingerprint=initial.broker_snapshot_fingerprint
            if fingerprint is not None:
                try:latest=self._risk_snapshot(request)
                except Exception:self.risk_gate.release(request.client_order_id);return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="RISK_BROKER_SNAPSHOT_UNAVAILABLE")
                if latest.broker_snapshot_fingerprint!=fingerprint:self.risk_gate.release(request.client_order_id);return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="RISK_BROKER_SNAPSHOT_CHANGED")
        except Exception:return ExecutionResult(request.client_order_id,OrderStatus.REJECTED.value,message="RISK_GATE_ERROR")
        return None
    def submit(self,request):
        safety_result=self._assert_safety_ready()
        if safety_result is not None:return ExecutionResult(request.client_order_id,safety_result.status,message=safety_result.message)
        with self._claim_lock:
            safety_result=self._assert_safety_ready()
            if safety_result is not None:return ExecutionResult(request.client_order_id,safety_result.status,message=safety_result.message)
            authorization_result=self._authorize_execution(request)
            if authorization_result is not None:return authorization_result
            existing=self.lifecycle.orders.get(request.client_order_id)
            if existing is not None and existing.status in {OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED}:return ExecutionResult(request.client_order_id,existing.status.value,existing.broker_order_id,"IDEMPOTENT_REPLAY")
            if not self.startup_state.execution_allowed:return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message=f"LIVE_EXECUTION_LOCKED_STARTUP_STATE_{self.startup_state.state.value}")
            if self.idempotency_store is not None and not self.idempotency_store.claim(request.client_order_id):
                recovered=self._recover_broker_order(request.client_order_id)
                if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED")
                return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION")
            recovered=self._recover_broker_order(request.client_order_id)
            if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED")
            self._create_lifecycle_record(request);self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMISSION_INTENT);self.store.save(self.lifecycle)
            risk_result=self._authorize_risk(request)
            if risk_result is not None:self.lifecycle.transition(request.client_order_id,OrderStatus.REJECTED);self.store.save(self.lifecycle);return risk_result
            try:
                result=self.router.submit(request);self._validate_submission_result(request,result);status=self._map_broker_status(str(result.status));filled=float(result.filled_quantity or 0) if result.filled_quantity is not None else 0.0;average=result.average_price if result.average_price is not None else result.price
                if status==OrderStatus.FILLED and abs(filled-float(request.quantity))>1e-9:raise RuntimeError("broker reported FILLED with incomplete quantity")
                self.lifecycle.transition(request.client_order_id,status,filled_quantity=filled,fill_price=average);self.lifecycle.orders[request.client_order_id].broker_order_id=result.order_id;self.store.save(self.lifecycle);self._settle_risk_reservation(request,status,self.lifecycle.orders[request.client_order_id].filled_quantity)
                if self.idempotency_store is not None and status!=OrderStatus.PARTIALLY_FILLED:self.idempotency_store.mark_completed(request.client_order_id)
                return ExecutionResult(request.client_order_id,status.value,result.order_id)
            except Exception:
                recovered=self._recover_broker_order(request.client_order_id)
                if recovered is not None:return self._save_recovered(request,recovered,"BROKER_ORDER_RECOVERED")
                self.lifecycle.transition(request.client_order_id,OrderStatus.SUBMITTED);self.store.save(self.lifecycle);return ExecutionResult(request.client_order_id,OrderStatus.SUBMITTED.value,message="EXECUTION_PENDING_RECONCILIATION")
