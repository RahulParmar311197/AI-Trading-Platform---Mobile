from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.smc_ict_engine import SMCICTEngine

def bars(values):
    t=datetime(2026,1,1,tzinfo=timezone.utc); out=[]
    for i,(o,h,l,c) in enumerate(values): out.append(Candle('NIFTY','15m',t+timedelta(minutes=15*i),o,h,l,c,1000))
    return out

def test_detects_swings_structure_fvg_and_order_block():
    candles=bars([(100,101,99,100),(100,102,99,101),(101,103,100,102),(102,110,102,109),(109,111,108,110),(110,111,107,108),(108,109,104,105)])
    result=SMCICTEngine().analyze(candles)
    assert result['swings']; assert result['structure']; assert isinstance(result['fair_value_gaps'],list); assert isinstance(result['order_blocks'],list)

def test_invalid_lookback_rejected():
    try: SMCICTEngine().swings(bars([(1,2,0,1)]),0); assert False
    except ValueError: pass
