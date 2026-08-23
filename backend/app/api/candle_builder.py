from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from app.candle_builder import CandleBuilder
router=APIRouter(prefix="/api/candles",tags=["live-candles"]); builder=CandleBuilder()
class Tick(BaseModel): symbol:str; timeframe:str; timestamp:datetime; price:float=Field(gt=0); volume:float=Field(default=0,ge=0)
def out(c): return None if c is None else {"symbol":c.symbol,"timeframe":c.timeframe,"start":c.start.isoformat(),"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume,"ticks":c.ticks}
@router.post("/tick")
def tick(p:Tick):
    try:
        r=builder.update_tick(p.symbol,p.timeframe,p.timestamp,p.price,p.volume); return {"current":out(r["current"]),"closed":out(r["closed"])}
    except ValueError as e: raise HTTPException(422,str(e))
@router.post("/flush")
def flush(): return {"candles":[out(c) for c in builder.flush()]}
