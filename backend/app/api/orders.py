from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.security import get_current_user
from app.broker_adapter import BrokerOrderRequest
from app.db import get_db
from app.models import Order, User
from app.risk_gate import PreTradeRiskGate, RiskLimits
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore
from app.execution_authorization import ExecutionAuthorization

router = APIRouter(prefix="/api/orders", tags=["orders"])

class OrderRequest(BaseModel):
    user_id:int|None=Field(default=None,gt=0)
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
    startup_state=getattr(request.app.state,"startup_execution_state",None)
    if startup_state is None and resources is not None: startup_state=resources.startup_execution_state
    if startup_state is not None and not startup_state.execution_allowed:
        raise HTTPException(status_code=409,detail={"code":"STARTUP_EXECUTION_LOCKED","reason":startup_state.status.reason or startup_state.state.value})

def get_order_db(request:Request,db:Session=Depends(get_db)):
    resources=getattr(request.app.state,"resources",None)
    if resources and resources.session_local is not None:
        session=resources.session_local()
        try: yield session
        finally: session.close()
    else: yield db

def _order_response(order:Order,message:str|None=None,execution_id:str|None=None)->dict:return {"id":order.id,"client_order_id":order.client_order_id,"broker_order_id":order.broker_order_id,"status":order.status,"message":message,"execution_id":execution_id}
def _set_execution_response_status(response:Response,status:str)->None:response.status_code=202 if status=="EXECUTION_PENDING_RECONCILIATION" else 201

def _commit_execution_intent(db:Session,order:Order)->None:
    """Durably commit the API order before any broker submission can occur."""
    try:
        db.commit()
        db.refresh(order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503,detail={"code":"ORDER_INTENT_PERSISTENCE_FAILED","reason":type(exc).__name__}) from exc

def _execution_service(broker_router,execution_store,idempotency_store,recovery,resources):
    from app.order_execution_service import OrderExecutionService
    from app.order_lifecycle import OrderLifecycle
    lifecycle=OrderLifecycle(resources.audit_log); execution_store.load(lifecycle); settings=__import__("app.config",fromlist=["get_settings"]).get_settings()
    gate=PreTradeRiskGate(RiskLimits(settings.risk_max_order_quantity,settings.risk_max_position_quantity,settings.risk_max_daily_loss,settings.risk_max_trade_loss)); provider=RuntimeRiskSnapshotProvider(broker_router,lifecycle,settings.risk_trading_day_timezone,settings.risk_max_snapshot_age_seconds)
    authorization=resources.authorization
    if authorization is None: authorization=ExecutionAuthorization(resources.safety_store,gate,provider,audit_log=resources.audit_log)
    startup_state=resources.startup_execution_state
    return OrderExecutionService(broker_router,lifecycle,execution_store,idempotency_store,recovery=recovery,risk_gate=gate,risk_snapshot_provider=provider,safety_state_store=resources.safety_store,authorization=authorization,startup_state=startup_state,audit_log=resources.audit_log)

def _broker_request(client_order_id,symbol,side,quantity,order_type="MARKET",price=None,stop=None,security_id="",owner_user_id=None):
    return BrokerOrderRequest(client_order_id=client_order_id,symbol=symbol,side=side,quantity=quantity,order_type=order_type,price=price,stop=stop,security_id=security_id,owner_user_id=owner_user_id)

@router.post("")
def create_order(payload:OrderRequest,request:Request,response:Response,db:Session=Depends(get_order_db),_:None=Depends(require_trading_ready),current_user:User=Depends(get_current_user),idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
    from app.startup_recovery import StartupRecoveryCoordinator
    resources=getattr(request.app.state,"resources",None)
    if resources is None: raise HTTPException(status_code=503,detail="EXECUTION_RESOURCES_UNAVAILABLE")
    if payload.user_id is not None and payload.user_id != current_user.id:
        raise HTTPException(status_code=403,detail="USER_IDENTITY_MISMATCH")
    user_id=current_user.id
    broker_router=request.app.state.broker_router; execution_store=resources.execution_store; idempotency_store=resources.idempotency_store
    recovery=getattr(request.app.state,"startup_recovery",None)
    if recovery is None: recovery=StartupRecoveryCoordinator(resources.startup_execution_state,resources.audit_log); request.app.state.startup_recovery=recovery
    client_order_id=idempotency_key.strip() if idempotency_key else str(uuid.uuid4())
    if not client_order_id or len(client_order_id)>128:raise HTTPException(status_code=422,detail="Idempotency-Key must be at most 128 characters")
    existing=db.query(Order).filter(Order.client_order_id==client_order_id,Order.user_id==user_id).first()
    if existing is not None:
        if existing.status in {"PENDING","SUBMISSION_INTENT","SUBMITTED","PARTIALLY_FILLED"} or existing.note=="EXECUTION_PENDING_RECONCILIATION":
            service=_execution_service(broker_router,execution_store,idempotency_store,recovery,resources)
            result=service.submit(_broker_request(client_order_id,existing.symbol,existing.side,existing.quantity,existing.order_type,existing.price,existing.stop,existing.security_id,existing.user_id))
            existing.status=result.status; existing.broker_order_id=result.broker_order_id; existing.note=result.message; db.commit(); db.refresh(existing); _set_execution_response_status(response,result.status); return _order_response(existing,result.message,result.execution_id)
        return _order_response(existing,"IDEMPOTENT_REPLAY")
    symbol=payload.symbol.upper(); order=Order(user_id=user_id,client_order_id=client_order_id,symbol=symbol,side=payload.side,quantity=payload.quantity,order_type=payload.order_type,price=payload.price,stop=payload.stop,security_id=payload.security_id,status="PENDING"); db.add(order)
    try:db.flush()
    except IntegrityError:
        db.rollback(); existing=db.query(Order).filter(Order.client_order_id==client_order_id,Order.user_id==user_id).first()
        if existing is None:raise HTTPException(status_code=409,detail="ORDER_CREATION_CONFLICT")
        return _order_response(existing,"IDEMPOTENT_REPLAY")
    _commit_execution_intent(db,order)
    service=_execution_service(broker_router,execution_store,idempotency_store,recovery,resources); result=service.submit(_broker_request(client_order_id,symbol,payload.side,payload.quantity,payload.order_type,payload.price,payload.stop,payload.security_id,user_id)); order.status=result.status; order.broker_order_id=result.broker_order_id; order.note=result.message; db.commit(); db.refresh(order); _set_execution_response_status(response,result.status); return _order_response(order,result.message,result.execution_id)
