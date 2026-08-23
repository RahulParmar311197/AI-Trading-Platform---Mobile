from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.technical_analysis import TechnicalAnalysisEngine

def candles(n=40):
    t=datetime(2026,1,1,tzinfo=timezone.utc); return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000+i) for i in range(n)]

def test_snapshot_produces_core_indicators():
    s=TechnicalAnalysisEngine().snapshot(candles()); assert s.ema_fast is not None; assert s.ema_slow is not None; assert s.rsi is not None; assert s.macd is not None; assert s.atr is not None; assert s.vwap is not None; assert s.bollinger_upper is not None; assert s.trend=='BULLISH'

def test_invalid_ema_period_rejected():
    try: TechnicalAnalysisEngine().ema([1,2,3],0); assert False
    except ValueError: pass
