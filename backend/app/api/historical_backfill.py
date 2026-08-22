from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from app.historical_market_store import HistoricalMarketStore
from app.historical_backfill import HistoricalBackfillEngine
router=APIRouter(prefix="/api/backfill",tags=["historical-backfill"])
store=HistoricalMarketStore()
def provider(symbol,timeframe,start,end): return []
engine=HistoricalBackfillEngine(store,provider)
class BackfillRequest(BaseModel): symbol:str; timeframe:str; start:datetime; end:datetime; step_seconds:int
@router.post("/check")
def check(p:BackfillRequest): return {'gaps':[{'start':g.start.isoformat(),'end':g.end.isoformat()} for g in engine.find_gaps(p.symbol,p.timeframe,p.start,p.end,p.step_seconds)]}
@router.post("/run")
def run(p:BackfillRequest): return engine.backfill(p.symbol,p.timeframe,p.start,p.end,p.step_seconds)
