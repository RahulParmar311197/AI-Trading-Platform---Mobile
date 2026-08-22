from fastapi import APIRouter
from app.schemas import OrderRequest, RiskConfig
from app.risk.engine import RiskEngine
router=APIRouter(tags=["risk"])
engine=RiskEngine()

@router.post("/risk/check")
def risk_check(order:OrderRequest, config:RiskConfig=RiskConfig()):
    d=engine.validate(order,config,equity=100000,daily_pnl=0,open_positions=0,trades_today=0)
    return {"approved":d.approved,"reasons":d.reasons}
