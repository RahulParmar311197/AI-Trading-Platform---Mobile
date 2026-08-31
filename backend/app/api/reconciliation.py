from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.db import SessionLocal, engine as database_engine
from app.reconciliation import ReconciliationEngine
from app.reconciliation_state_store import ReconciliationStateStore
from app.risk_reservation_store import RiskReservationStore

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])
state_store = ReconciliationStateStore(engine=database_engine)
risk_reservation_store = RiskReservationStore(SessionLocal)
engine = ReconciliationEngine(state_store=state_store, risk_reservation_store=risk_reservation_store)


class ReconcileRequest(BaseModel):
    broker_account_id: str = Field(min_length=1, max_length=128)
    broker_route: str = Field(min_length=1, max_length=160)
    internal_orders: list[dict] = Field(default_factory=list)
    broker_orders: list[dict] = Field(default_factory=list)
    internal_positions: list[dict] = Field(default_factory=list)
    broker_positions: list[dict] = Field(default_factory=list)


@router.post("/check")
def check(p: ReconcileRequest):
    result = engine.check(
        p.internal_orders,
        p.broker_orders,
        p.internal_positions,
        p.broker_positions,
        broker_account_id=p.broker_account_id,
        broker_route=p.broker_route,
    )
    return result.__dict__


@router.get("/status")
def status(
    broker_account_id: str = Query(min_length=1, max_length=128),
    broker_route: str = Query(min_length=1, max_length=160),
):
    state = state_store.get_state(broker_account_id=broker_account_id, broker_route=broker_route)
    return {
        "broker_account_id": state.broker_account_id,
        "broker_route": state.broker_route,
        "status": state.status,
        "trading_halted": state.trading_halted,
        "checked_at": state.checked_at,
        "order_drift_count": state.order_drift_count,
        "position_drift_count": state.position_drift_count,
    }
