from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.ensemble import decide
from app.market_data import market_data
from app.broker_adapter import BrokerOrderRequest
from app.decision_execution_guard import execute_decision
from app.safety_state import SafetyStateStore
from app.execution_authorization import ExecutionAuthorization
from app.config import get_settings

router=APIRouter(prefix="/api/decision",tags=["ai-decision"])

class DecisionExecuteRequest(BaseModel):
    user_id:int=Field(gt=0)
    symbol:str=Field(min_length=1,max_length=64)
    timeframe:str=Field(default="5m",min_length=1,max_length=16)
    quantity:float=Field(gt=0)
    client_order_id:str=Field(min_length=1,max_length=128)
    limit:int=Field(default=200,ge=2,le=5000)

def require_trading_ready(request:Request)->None:
    resources=getattr(request.app.state,"resources",None)
    safety_store=resources.safety_store if resources and hasattr(resources,"safety_store") else SafetyStateStore()
    state=safety_store.load()
    if state.trading_halted:
        raise HTTPException(status_code=409,detail={"code":"TRADING_HALTED","reason":state.halt_reason})

@router.get("")
def decision(symbol:str,timeframe:str="5m",limit:int=200):
    try:
        settings=get_settings()
        candles=market_data.candles(symbol,timeframe,min(limit,5000))
        result=decide(candles,confluence_weight=settings.ai_confluence_weight)
        return {"symbol":symbol.upper(),"timeframe":timeframe,**result.__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

@router.post("/execute")
def execute(request:Request,payload:DecisionExecuteRequest):
    require_trading_ready(request)
    try:
        candles=market_data.candles(payload.symbol,payload.timeframe,payload.limit)
        settings=get_settings()
        decision_result=decide(candles,confluence_weight=settings.ai_confluence_weight)
        resources=getattr(request.app.state,"resources",None)
        broker_router=request.app.state.broker_router
        execution_store=resources.execution_store
        idempotency_store=resources.idempotency_store
        from app.order_execution_service import OrderExecutionService
        from app.order_lifecycle import OrderLifecycle
        from app.startup_recovery import StartupRecoveryCoordinator
        from app.risk_gate import PreTradeRiskGate,RiskLimits
        from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
        lifecycle=OrderLifecycle(); execution_store.load(lifecycle)
        risk_gate=PreTradeRiskGate(RiskLimits(settings.risk_max_order_quantity,settings.risk_max_position_quantity,settings.risk_max_daily_loss,settings.risk_max_trade_loss))
        provider=RuntimeRiskSnapshotProvider(broker_router,lifecycle,settings.risk_trading_day_timezone,settings.risk_max_snapshot_age_seconds)
        authorization=resources.authorization or ExecutionAuthorization(resources.safety_store,risk_gate,provider)
        service=OrderExecutionService(broker_router,lifecycle,execution_store,idempotency_store,recovery=StartupRecoveryCoordinator(),risk_gate=risk_gate,risk_snapshot_provider=provider,safety_state_store=resources.safety_store,authorization=authorization)
        guarded=execute_decision(decision_result,service,lambda action:BrokerOrderRequest(client_order_id=payload.client_order_id,symbol=payload.symbol.upper(),side=action,quantity=payload.quantity))
        return {"executed":guarded.executed,"decision":decision_result.__dict__,"execution":guarded.result.__dict__ if guarded.result else None,"reason":guarded.reason}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
