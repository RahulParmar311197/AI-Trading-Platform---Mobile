from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.security import get_current_user
from app.broker_adapter import BrokerOrderRequest
from app.broker_factory import account_route_generation, account_route_name
from app.config import get_settings
from app.db import SessionLocal
from app.ensemble import decide
from app.execution_authorization import ExecutionAuthorization
from app.market_data import market_data
from app.models import BrokerAccount, User
from app.risk_gate import PreTradeRiskGate, RiskLimits
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore
from app.decision_execution_guard import execute_decision

router = APIRouter(prefix="/api/decision", tags=["ai-decision"])


class DecisionExecuteRequest(BaseModel):
    user_id: int = Field(gt=0)
    broker_account_id: int | None = Field(default=None, gt=0)
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(default="5m", min_length=1, max_length=16)
    quantity: float = Field(gt=0)
    client_order_id: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=200, ge=2, le=5000)


def require_trading_ready(request: Request) -> None:
    resources = getattr(request.app.state, "resources", None)
    safety_store = resources.safety_store if resources and hasattr(resources, "safety_store") else SafetyStateStore()
    state = safety_store.load()
    if state.trading_halted:
        raise HTTPException(status_code=409, detail={"code": "TRADING_HALTED", "reason": state.halt_reason})
    startup_state = getattr(request.app.state, "startup_execution_state", None)
    if startup_state is None and resources is not None:
        startup_state = getattr(resources, "startup_execution_state", None)
    if startup_state is not None and not startup_state.execution_allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STARTUP_EXECUTION_LOCKED",
                "reason": startup_state.status.reason or startup_state.state.value,
            },
        )


def _resolve_broker_account(user_id: int, requested_id: int | None) -> BrokerAccount:
    with SessionLocal() as db:
        if requested_id is not None:
            account = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.id == requested_id,
                    BrokerAccount.user_id == user_id,
                    BrokerAccount.status == "active",
                )
                .first()
            )
            if account is None:
                raise HTTPException(status_code=403, detail="BROKER_ACCOUNT_NOT_OWNED_OR_ACTIVE")
            db.expunge(account)
            return account

        accounts = (
            db.query(BrokerAccount)
            .filter(BrokerAccount.user_id == user_id, BrokerAccount.status == "active")
            .order_by(BrokerAccount.id.asc())
            .all()
        )
        if not accounts:
            raise HTTPException(status_code=409, detail="BROKER_ACCOUNT_REQUIRED")
        if len(accounts) != 1:
            raise HTTPException(status_code=409, detail="BROKER_ACCOUNT_SELECTION_REQUIRED")
        account = accounts[0]
        db.expunge(account)
        return account


def _execution_service(broker_router, resources):
    from app.order_execution_service import OrderExecutionService
    from app.order_lifecycle import OrderLifecycle
    from app.startup_recovery import StartupRecoveryCoordinator

    settings = get_settings()
    lifecycle = OrderLifecycle(resources.audit_log)
    resources.execution_store.load(lifecycle)
    risk_gate = PreTradeRiskGate(
        RiskLimits(
            settings.risk_max_order_quantity,
            settings.risk_max_position_quantity,
            settings.risk_max_daily_loss,
            settings.risk_max_trade_loss,
        )
    )
    provider = RuntimeRiskSnapshotProvider(
        broker_router,
        lifecycle,
        settings.risk_trading_day_timezone,
        settings.risk_max_snapshot_age_seconds,
    )
    authorization = resources.authorization
    if authorization is None:
        authorization = ExecutionAuthorization(
            resources.safety_store,
            risk_gate,
            provider,
            audit_log=resources.audit_log,
        )
    recovery = getattr(resources, "startup_recovery", None) or StartupRecoveryCoordinator()
    return OrderExecutionService(
        broker_router,
        lifecycle,
        resources.execution_store,
        resources.idempotency_store,
        recovery=recovery,
        risk_gate=risk_gate,
        risk_snapshot_provider=provider,
        safety_state_store=resources.safety_store,
        authorization=authorization,
        startup_state=resources.startup_execution_state,
        audit_log=resources.audit_log,
        observability=resources.execution_observability,
        connectivity_registry=resources.connectivity_registry,
    )


@router.get("")
def decision(symbol: str, timeframe: str = "5m", limit: int = 200):
    try:
        settings = get_settings()
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        result = decide(candles, confluence_weight=settings.ai_confluence_weight)
        return {"symbol": symbol.upper(), "timeframe": timeframe, **result.__dict__}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/execute")
def execute(
    request: Request,
    payload: DecisionExecuteRequest,
    current_user: User = Depends(get_current_user),
):
    require_trading_ready(request)
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="USER_IDENTITY_MISMATCH")

    resources = getattr(request.app.state, "resources", None)
    if resources is None:
        raise HTTPException(status_code=503, detail="EXECUTION_RESOURCES_UNAVAILABLE")

    try:
        settings = get_settings()
        account = _resolve_broker_account(current_user.id, payload.broker_account_id)
        broker_route = account_route_name(account)
        broker_route_generation = account_route_generation(account)
        broker_router = request.app.state.broker_router
        route = broker_router.get(broker_route)
        if route.broker_account_id != int(account.id) or route.generation != broker_route_generation:
            raise HTTPException(status_code=409, detail="BROKER_ACCOUNT_ROUTE_STALE")

        candles = market_data.candles(payload.symbol, payload.timeframe, payload.limit)
        decision_result = decide(candles, confluence_weight=settings.ai_confluence_weight)
        service = _execution_service(broker_router, resources)
        guarded = execute_decision(
            decision_result,
            service,
            lambda action: BrokerOrderRequest(
                client_order_id=payload.client_order_id,
                symbol=payload.symbol.upper(),
                side=action,
                quantity=payload.quantity,
                owner_user_id=current_user.id,
                broker_account_id=int(account.id),
                broker_route=broker_route,
                broker_route_generation=broker_route_generation,
            ),
        )
        return {
            "executed": guarded.executed,
            "decision": decision_result.__dict__,
            "execution": guarded.result.__dict__ if guarded.result else None,
            "reason": guarded.reason,
            "broker_account_id": int(account.id),
            "broker_route": broker_route,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
