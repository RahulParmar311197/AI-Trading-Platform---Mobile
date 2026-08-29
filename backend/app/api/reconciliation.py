from fastapi import APIRouter
from pydantic import BaseModel
from app.reconciliation import ReconciliationEngine

router=APIRouter(prefix="/api/reconciliation",tags=["reconciliation"])
engine=ReconciliationEngine()
class ReconcileRequest(BaseModel):
    internal_orders:list[dict]=[]; broker_orders:list[dict]=[]; internal_positions:list[dict]=[]; broker_positions:list[dict]=[]
@router.post("/check")
def check(p:ReconcileRequest): return engine.check(p.internal_orders,p.broker_orders,p.internal_positions,p.broker_positions).__dict__
@router.get("/status")
def status(): return {"trading_halted":engine.trading_halted}
