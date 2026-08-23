from datetime import datetime, timedelta, timezone
import random
import pandas as pd
from fastapi import APIRouter, Query
from app.smc.engine import analyze

router=APIRouter(tags=["markets"])

def demo_candles(symbol:str, n:int=200):
    price=25000.0 if symbol.upper()=="NIFTY" else 50000.0
    rows=[]; now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
    for i in range(n):
        o=price; c=max(1,o+random.uniform(-80,80)); h=max(o,c)+random.uniform(0,35); l=min(o,c)-random.uniform(0,35)
        rows.append({"symbol":symbol,"timestamp":now-timedelta(minutes=n-i),"timeframe":"1m","open":o,"high":h,"low":l,"close":c,"volume":random.randint(1000,100000)})
        price=c
    return rows

@router.get("/markets")
def markets():
    return [{"symbol":"NIFTY","exchange":"NSE","market":"EQUITY_INDEX"},{"symbol":"BANKNIFTY","exchange":"NSE","market":"EQUITY_INDEX"},{"symbol":"BTC/USDT","exchange":"CRYPTO","market":"CRYPTO"}]

@router.get("/candles")
def candles(symbol:str=Query("NIFTY"), limit:int=Query(200,ge=20,le=2000)):
    return demo_candles(symbol,limit)

@router.get("/analysis")
def market_analysis(symbol:str=Query("NIFTY"), limit:int=Query(200,ge=20,le=2000)):
    data=demo_candles(symbol,limit); df=pd.DataFrame(data); result=analyze(df)
    return {"symbol":symbol,"timeframe":"1m",**result}
