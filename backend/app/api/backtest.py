import pandas as pd
from fastapi import APIRouter
from app.api.markets import demo_candles
from app.backtest.engine import run
router=APIRouter(tags=["backtest"])

@router.post("/backtest")
def backtest(symbol:str="NIFTY", bars:int=1000, capital:float=100000, risk_percent:float=0.5):
    df=pd.DataFrame(demo_candles(symbol,min(max(bars,50),2000)))
    return run(df,capital,risk_percent/100)
