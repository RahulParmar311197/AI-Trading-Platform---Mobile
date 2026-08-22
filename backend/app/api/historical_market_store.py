from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.historical_market_store import HistoricalMarketStore
from app.mtf_aggregator import Candle
router=APIRouter(prefix="/api/history",tags=["historical-market-data"]); store=HistoricalMarketStore()
class CandleIn(BaseModel): timestamp:datetime; open:float; high:float; low:float; close:float; volume:float
class UpsertRequest(BaseModel): symbol:str; timeframe:str; candles:list[CandleIn]
@router.post("/upsert")
def upsert(p:UpsertRequest):
    try:
        items=[Candle(x.timestamp,x.open,x.high,x.low,x.close,x.volume,p.symbol.upper(),p.timeframe) for x in p.candles]
        return {"stored":store.upsert(items)}
    except ValueError as e: raise HTTPException(422,str(e))
@router.get("/{symbol}/{timeframe}")
def query(symbol:str,timeframe:str,start:datetime|None=None,end:datetime|None=None,limit:int=5000): return {"candles":store.query(symbol,timeframe,start,end,limit),"count":store.count(symbol,timeframe)}
