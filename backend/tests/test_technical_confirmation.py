from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.technical_confirmation import TechnicalConfirmationEngine

def candles(n=40):
 t=datetime(2026,1,1,tzinfo=timezone.utc); return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000+i*5) for i in range(n)]

def test_confirmation_has_core_context():
 r=TechnicalConfirmationEngine().analyze(candles()); assert r.adx is not None; assert r.support is not None; assert r.resistance is not None; assert r.volume_ratio is not None; assert r.bias in {'BULLISH','BEARISH','NEUTRAL'}

def test_empty_is_neutral():
 r=TechnicalConfirmationEngine().analyze([]); assert r.bias=='NEUTRAL'; assert r.score==0
