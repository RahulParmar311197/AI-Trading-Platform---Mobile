from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.liquidity_engine import LiquidityEngine,DealingRange

def bars(values):
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),o,h,l,c,100) for i,(o,h,l,c) in enumerate(values)]

def test_dealing_range_and_zones():
    e=LiquidityEngine(); dr=e.dealing_range(bars([(100,110,95,105),(105,108,100,106)])); assert dr==DealingRange(110,95,102.5); assert e.zone(105,dr)=='PREMIUM'; assert e.zone(100,dr)=='DISCOUNT'

def test_detects_liquidity_sweeps():
    c=bars([(100,105,99,104)]*10+[(104,107,101,103),(103,104,97,102)])
    result=LiquidityEngine().analyze(c); assert result['sweeps']

def test_invalid_lookback_rejected():
    try: LiquidityEngine().sweeps(bars([(1,2,0,1)]),0); assert False
    except ValueError: pass
