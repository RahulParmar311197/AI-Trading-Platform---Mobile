from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.historical_market_store import HistoricalMarketStore
from app.historical_backfill import HistoricalBackfillEngine
from app.backfill_orchestrator import OrchestratedBackfill
from app.provider_bootstrap import build_provider_orchestrator
router=APIRouter(prefix="/api/backfill",tags=["historical-backfill"])
store=HistoricalMarketStore()
provider_orchestrator=build_provider_orchestrator()
class BackfillRequest(BaseModel):
    symbol:str
    timeframe:str
    start:datetime
    end:datetime
    step_seconds:int
engine=HistoricalBackfillEngine(store,lambda *args: [])
@router.post("/check")
def check(p:BackfillRequest):
    return {'gaps':[{'start':g.start.isoformat(),'end':g.end.isoformat()} for g in engine.find_gaps(p.symbol,p.timeframe,p.start,p.end,p.step_seconds)]}
@router.post("/run")
async def run(p:BackfillRequest):
    if p.start>p.end: raise HTTPException(400,"start must be before end")
    result=await OrchestratedBackfill(provider_orchestrator,store).run(p.symbol,p.timeframe,p.start,p.end,p.step_seconds)
    return result
