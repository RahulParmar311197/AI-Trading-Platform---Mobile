from datetime import datetime, timedelta, timezone
import random
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from app.smc.engine import analyze
from app.provider_bootstrap import build_provider_orchestrator

router=APIRouter(tags=["markets"])

def demo_candles(symbol:str, n:int=200):
    price=25000.0 if symbol.upper()=="NIFTY" else 50000.0
    rows=[]; now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
    for i in range(n):
        o=price; c=max(1,o+random.uniform(-80,80)); h=max(o,c)+random.uniform(0,35); l=min(o,c)-random.uniform(0,35)
        rows.append({"symbol":symbol,"timestamp":now-timedelta(minutes=n-i),"timeframe":"1m","open":o,"high":h,"low":l,"close":c,"volume":random.randint(1000,100000)})
        price=c
    return rows

def _serialize_provider_candles(symbol:str, timeframe:str, candles):
    return [{"symbol":symbol,"timestamp":c.timestamp,"timeframe":timeframe,"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume} for c in candles]

async def _provider_candles(symbol:str, timeframe:str, limit:int):
    end=datetime.now(timezone.utc)
    minutes={"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240,"1d":1440}.get(timeframe,5)
    start=end-timedelta(minutes=int(minutes*limit*1.25))
    try:
        candles=await build_provider_orchestrator().historical(symbol,timeframe,start,end)
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"market provider unavailable: {exc}") from exc
    if not candles:
        raise HTTPException(status_code=503,detail="market provider returned no candles")
    return _serialize_provider_candles(symbol,timeframe,candles[-limit:])

@router.get("/markets")
def markets():
    return [{"symbol":"NIFTY","exchange":"NSE","market":"EQUITY_INDEX"},{"symbol":"BANKNIFTY","exchange":"NSE","market":"EQUITY_INDEX"},{"symbol":"BTC/USDT","exchange":"CRYPTO","market":"CRYPTO"}]

@router.get("/candles")
async def candles(symbol:str=Query("NIFTY"), timeframe:str=Query("5m"), limit:int=Query(200,ge=20,le=2000), demo:bool=Query(False)):
    if demo:
        return demo_candles(symbol,limit)
    return await _provider_candles(symbol,timeframe,limit)

@router.get("/analysis")
async def market_analysis(symbol:str=Query("NIFTY"), timeframe:str=Query("5m"), limit:int=Query(200,ge=20,le=2000), demo:bool=Query(False)):
    data=demo_candles(symbol,limit) if demo else await _provider_candles(symbol,timeframe,limit)
    df=pd.DataFrame(data); result=analyze(df)
    return {"symbol":symbol,"timeframe":timeframe,**result}
