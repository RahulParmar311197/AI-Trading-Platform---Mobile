from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.unified_signal import UnifiedSignalEngine,SignalWeights

def bars(n=60):
 t=datetime(2026,1,1,tzinfo=timezone.utc); return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000+i*5) for i in range(n)]

def test_unified_signal_shape():
 r=UnifiedSignalEngine().analyze(bars()); assert r['direction'] in {'BULLISH','BEARISH','NEUTRAL'}; assert 0<=r['confidence']<=1; assert isinstance(r['reasons'],list)

def test_empty_data_not_tradeable():
 r=UnifiedSignalEngine().analyze([]); assert not r['tradeable']; assert r['direction']=='NEUTRAL'

def test_high_threshold_filters_signal():
 r=UnifiedSignalEngine(SignalWeights(threshold=2)).analyze(bars()); assert not r['tradeable']
