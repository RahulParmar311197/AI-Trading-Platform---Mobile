from __future__ import annotations
import math
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.security import get_current_user
from app.broker_adapter import BrokerOrderRequest, normalize_broker_update, BrokerOrderStatus
from app.broker_factory import account_route_generation
from app.db import get_db
from app.models import BrokerAccount, Order, User
from app.risk_gate import PreTradeRiskGate, RiskLimits
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore
from app.execution_authorization import ExecutionAuthorization

router = APIRouter(prefix="/api/orders", tags=["orders"])

class OrderRequest(BaseModel):
    user_id:int|None=Field(default=None,gt=0)
    broker_account_id:int|None=Field(default=None,gt=0)
    symbol:str=Field(min_length=1,max_length=64)
    side:str=Field(pattern="^(BUY|SELL)$")
    quantity:float=Field(gt=0)
    order_type:str=Field(default="MARKET",pattern="^(MARKET|LIMIT|SL)$")
    price:float|None=Field(default=None,gt=0)
    stop:float|None=Field(default=None,gt=0)
    security_id:str=Field(default="",max_length=128)

def require_trading_ready(request:Request)->None:
    resources=getattr(request.app.state,"resources",None); safety_store=resources.safety_store if resources else SafetyStateStore(); state=safety_store.load()
    if state.trading_halted: raise HTTPException(status_code=409,detail={"code":"TRADING_HALTED","reason":state.halt_reason})
    circuit_breaker=getattr(request.app.state,"risk_circuit_breaker",None)
    if circuit_breaker is None and resources is not None: circuit_breaker=getattr(resources,"risk_circuit_breaker",None)
    if circuit_breaker is not None:
        circuit_status=circuit_breaker.status()
        if circuit_status.blocked: raise HTTPException(status_code=409,detail={"code":"RISK_CIRCUIT_BREAKER_BLOCKED","reason":circuit_status.reason or "risk circuit breaker engaged"})
    startup_state=getattr(request.app.state,"startup_execution_state",None)
    if startup_state is None and resources is not None: startup_state=resources.startup_execution_state
    if startup_state is not None and not startup_state.execution_allowed: raise HTTPException(status_code=409,detail={"code":"STARTUP_EXECUTION_LOCKED","reason":startup_state.status.reason or startup_state.state.value})

def get_order_db(request:Request,db:Session=Depends(get_db)):
    resources=getattr(request.app.state,"resources",None)
    if resources and resources.session_local is not None:
        session=resources.session_local()
        try: yield session
        finally: session.close()
    else: yield db

def _order_response(order:Order,message:str|None=None,execution_id:str|None=None)->dict:return {"id":order.id,"client_order_id":order.client_order_id,"broker_order_id":order.broker_order_id,"status":order.status,"message":message,"execution_id":execution_id,"broker_account_id":order.broker_account_id}
def _set_execution_response_status(response:Response,status:str)->None:response.status_code=202 if status=="EXECUTION_PENDING_RECONCILIATION" else 201

def _commit_execution_intent(db:Session,order:Order)->None:
    try: db.commit(); db.refresh(order)
    except Exception as exc: db.rollback(); raise HTTPException(status_code=503,detail={"code":"ORDER_INTENT_PERSISTENCE_FAILED","reason":type(exc).__name__}) from exc

def _commit_execution_projection(db:Session,order:Order)->None:
    try: db.commit(); db.refresh(order)
    except Exception as exc: db.rollback(); raise HTTPException(status_code=503,detail={"code":"EXECUTION_PROJECTION_PERSISTENCE_FAILED","reason":type(exc).__name__,"client_order_id":order.client_order_id,"reconciliation_required":True}) from exc

def _execution_service(broker_router,execution_store,idempotency_store,recovery,resources):
    from app.order_execution_service import OrderExecutionService
    from app.order_lifecycle import OrderLifecycle
    lifecycle=OrderLifecycle(resources.audit_log); execution_store.load(lifecycle); settings=__import__("app.config",fromlist=["get_settings"]).get_settings()
    gate=PreTradeRiskGate(RiskLimits(settings.risk_max_order_quantity,settings.risk_max_position_quantity,settings.risk_max_daily_loss,settings.risk_max_trade_loss)); provider=RuntimeRiskSnapshotProvider(broker_router,lifecycle,settings.risk_trading_day_timezone,settings.risk_max_snapshot_age_seconds)
    authorization=resources.authorization
    if authorization is None: authorization=ExecutionAuthorization(resources.safety_store,gate,provider,audit_log=resources.audit_log)
    startup_state=resources.startup_execution_state
    return OrderExecutionService(broker_router,lifecycle,execution_store,idempotency_store,recovery=recovery,risk_gate=gate,risk_snapshot_provider=provider,safety_state_store=resources.safety_store,authorization=authorization,startup_state=startup_state,audit_log=resources.audit_log,observability=resources.execution_observability,connectivity_registry=resources.connectivity_registry)

def _broker_request(client_order_id,symbol,side,quantity,order_type="MARKET",price=None,stop=None,security_id="",owner_user_id=None,broker_account_id=None,broker_route=None,broker_route_generation=None):
    return BrokerOrderRequest(client_order_id=client_order_id,symbol=symbol,side=side,quantity=quantity,order_type=order_type,price=price,stop=stop,security_id=security_id,owner_user_id=owner_user_id,broker_account_id=broker_account_id,broker_route=broker_route,broker_route_generation=broker_route_generation)

def _broker_route_for_account(account:BrokerAccount)->str:
    broker=str(account.broker).strip().lower()
    if not broker or account.id is None or int(account.id)<=0: raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_ROUTE_UNAVAILABLE")
    return f"{broker}:account:{int(account.id)}"

def _resolve_broker_account(db:Session,user_id:int,requested_id:int|None)->BrokerAccount:
    if requested_id is not None:
        account=db.query(BrokerAccount).filter(BrokerAccount.id==requested_id,BrokerAccount.user_id==user_id,BrokerAccount.status=="active").first()
        if account is None: raise HTTPException(status_code=403,detail="BROKER_ACCOUNT_NOT_OWNED_OR_ACTIVE")
        return account
    accounts=db.query(BrokerAccount).filter(BrokerAccount.user_id==user_id,BrokerAccount.status=="active").all()
    if len(accounts)==1: return accounts[0]
    if not accounts: raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_REQUIRED")
    raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_SELECTION_REQUIRED")

def _project_authoritative_broker_update(order:Order,result)->None:
    """Project authoritative broker fill data without allowing fabricated values."""
    if result.filled_quantity is not None:
        filled=float(result.filled_quantity)
        if not math.isfinite(filled) or filled < 0 or filled > float(order.quantity)+1e-9:
            raise ValueError("broker cancellation fill quantity is invalid")
        order.filled_quantity=filled
    if result.average_price is not None:
        average=float(result.average_price)
        if not math.isfinite(average) or average <= 0:
            raise ValueError("broker cancellation average price is invalid")
        order.average_fill_price=average

def _matches_order_broker_identity(order:Order,result)->bool:
    """Compare broker identities without coercing opaque external identifiers to integers."""
    if result.broker_account_id is not None and str(result.broker_account_id).strip() != str(order.broker_account_id).strip():
        return False
    if result.broker_route is not None and result.broker_route != order.broker_route:
        return False
    if result.broker_route_generation is not None and result.broker_route_generation != order.broker_route_generation:
        return False
    return True

def _authoritative_cancel_result(broker_router,order):
    """Cancel through the exact broker order binding and reconcile final state."""
    from app.authoritative_cancel import AuthoritativeCancelReconciler
    return AuthoritativeCancelReconciler().cancel_and_reconcile(broker_router, order)

def _reconcile_risk_reservation(resources, client_order_id:str, broker_status:str, remaining_amount:float|None=None)->None:
    store=getattr(resources,"risk_reservation_store",None)
    if store is None:
        return
    try:
        store.reconcile_client_order(client_order_id=client_order_id, broker_status=broker_status, remaining_amount=remaining_amount)
    except Exception as exc:
        raise HTTPException(status_code=503,detail={"code":"RISK_RESERVATION_RECONCILIATION_FAILED","reason":type(exc).__name__,"client_order_id":client_order_id,"reconciliation_required":True}) from exc

@router.post("")
def create_order(payload:OrderRequest,request:Request,response:Response,db:Session=Depends(get_order_db),_:None=Depends(require_trading_ready),current_user:User=Depends(get_current_user),idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
    from app.startup_recovery import StartupRecoveryCoordinator
    resources=getattr(request.app.state,"resources",None)
    if resources is None: raise HTTPException(status_code=503,detail="EXECUTION_RESOURCES_UNAVAILABLE")
    if payload.user_id is not None and payload.user_id != current_user.id: raise HTTPException(status_code=403,detail="USER_IDENTITY_MISMATCH")
    user_id=current_user.id; broker_router=request.app.state.broker_router; execution_store=resources.execution_store; idempotency_store=resources.idempotency_store; recovery=getattr(request.app.state,"startup_recovery",None)
    if recovery is None: recovery=StartupRecoveryCoordinator(resources.startup_execution_state,resources.audit_log); request.app.state.startup_recovery=recovery
    client_order_id=idempotency_key.strip() if idempotency_key else str(uuid.uuid4())
    if not client_order_id or len(client_order_id)>128: raise HTTPException(status_code=422,detail="Idempotency-Key must be at most 128 characters")
    existing=db.query(Order).filter(Order.client_order_id==client_order_id,Order.user_id==user_id).first()
    if existing is not None:
        if existing.status in {"PENDING","SUBMISSION_INTENT","SUBMITTED","PARTIALLY_FILLED"} or existing.note=="EXECUTION_PENDING_RECONCILIATION":
            if existing.broker_account_id is None or not existing.broker_route or not existing.broker_route_generation: raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_BINDING_MISSING_OR_STALE")
            service=_execution_service(broker_router,execution_store,idempotency_store,recovery,resources); result=service.submit(_broker_request(client_order_id,existing.symbol,existing.side,existing.quantity,existing.order_type,existing.price,existing.stop,existing.security_id,existing.user_id,existing.broker_account_id,existing.broker_route,existing.broker_route_generation)); existing.status=result.status; existing.broker_order_id=result.broker_order_id; existing.note=result.message; _commit_execution_projection(db,existing); _set_execution_response_status(response,result.status); return _order_response(existing,result.message,result.execution_id)
        return _order_response(existing,"IDEMPOTENT_REPLAY")
    account=_resolve_broker_account(db,user_id,payload.broker_account_id); broker_route=_broker_route_for_account(account); route_generation=account_route_generation(account)
    try: broker_router.get(broker_route)
    except Exception as exc: raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_ROUTE_UNAVAILABLE") from exc
    symbol=payload.symbol.upper(); order=Order(user_id=user_id,broker_account_id=account.id,broker_route=broker_route,broker_route_generation=route_generation,client_order_id=client_order_id,symbol=symbol,side=payload.side,quantity=payload.quantity,order_type=payload.order_type,price=payload.price,stop=payload.stop,security_id=payload.security_id,status="PENDING"); db.add(order)
    try: db.flush()
    except IntegrityError:
        db.rollback(); existing=db.query(Order).filter(Order.client_order_id==client_order_id,Order.user_id==user_id).first()
        if existing is None: raise HTTPException(status_code=409,detail="ORDER_CREATION_CONFLICT")
        return _order_response(existing,"IDEMPOTENT_REPLAY")
    _commit_execution_intent(db,order)
    service=_execution_service(broker_router,execution_store,idempotency_store,recovery,resources); result=service.submit(_broker_request(client_order_id,symbol,payload.side,payload.quantity,payload.order_type,payload.price,payload.stop,payload.security_id,user_id,account.id,broker_route,route_generation)); order.status=result.status; order.broker_order_id=result.broker_order_id; order.note=result.message; _commit_execution_projection(db,order); _set_execution_response_status(response,result.status); return _order_response(order,result.message,result.execution_id)

@router.delete("/{client_order_id}")
def cancel_order(client_order_id:str,request:Request,response:Response,db:Session=Depends(get_order_db),current_user:User=Depends(get_current_user)):
    """Cancel an owned live order and require an authoritative post-cancel broker read."""
    normalized=client_order_id.strip()
    if not normalized or len(normalized)>128: raise HTTPException(status_code=422,detail="client_order_id is required")
    order=db.query(Order).filter(Order.client_order_id==normalized).first()
    if order is None: raise HTTPException(status_code=404,detail="ORDER_NOT_FOUND")
    if order.user_id != current_user.id: raise HTTPException(status_code=403,detail="ORDER_NOT_OWNED")
    if order.broker_account_id is None or not order.broker_route or not order.broker_route_generation:
        raise HTTPException(status_code=409,detail="BROKER_ACCOUNT_BINDING_MISSING_OR_STALE")
    if not order.broker_order_id:
        raise HTTPException(status_code=409,detail={"code":"BROKER_ORDER_ID_UNAVAILABLE","reconciliation_required":True})
    if order.status in {"CANCELLED","REJECTED","FILLED"}:
        return _order_response(order,"CANCEL_IDEMPOTENT_NOOP")
    broker_router=getattr(request.app.state,"broker_router",None)
    if broker_router is None: raise HTTPException(status_code=503,detail="BROKER_ROUTER_UNAVAILABLE")
    resources=getattr(request.app.state,"resources",None)
    if resources is None: raise HTTPException(status_code=503,detail="EXECUTION_RESOURCES_UNAVAILABLE")
    try:
        reconciliation=_authoritative_cancel_result(broker_router,order)
        result=reconciliation.update
        _project_authoritative_broker_update(order,result)
        _reconcile_risk_reservation(resources,order.client_order_id,result.status,remaining_amount=0.0 if result.status in {BrokerOrderStatus.CANCELLED.value,BrokerOrderStatus.FILLED.value,BrokerOrderStatus.REJECTED.value} else None)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail={"code":"BROKER_CANCEL_RESPONSE_INVALID","reason":str(exc),"reconciliation_required":True}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409,detail={"code":"BROKER_CANCEL_RECONCILIATION_REQUIRED","reason":str(exc),"reconciliation_required":True}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502,detail={"code":"BROKER_CANCEL_FAILED","reason":type(exc).__name__,"reconciliation_required":True}) from exc
    order.status=result.status
    order.note="BROKER_CANCEL_CONFIRMED" if result.status==BrokerOrderStatus.CANCELLED.value else f"BROKER_CANCEL_RACE_{result.status}"
    if result.order_id:
        order.broker_order_id=result.order_id
    try:
        db.commit(); db.refresh(order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503,detail={"code":"CANCELLATION_PROJECTION_PERSISTENCE_FAILED","client_order_id":order.client_order_id,"reconciliation_required":True}) from exc
    response.status_code=200
    return _order_response(order,order.note)
