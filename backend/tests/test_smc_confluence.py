from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.smc_confluence import SMCConfluenceEngine,ConfluenceWeights

def bars():
    t=datetime(2026,1,1,tzinfo=timezone.utc); values=[(100,101,99,100),(100,102,99,101),(101,103,100,102),(102,110,102,109),(109,111,108,110),(110,111,107,108),(108,109,104,105)]
    return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),o,h,l,c,100) for i,(o,h,l,c) in enumerate(values)]

def test_confluence_returns_bounded_confidence_and_components():
    r=SMCConfluenceEngine().analyze(bars()); assert r['bias'] in {'BULLISH','BEARISH','NEUTRAL'}; assert 0<=r['confidence']<=1; assert set(r['components'])=={'structure','fvg','order_block','liquidity_sweep','zone'}

def test_empty_data_is_neutral():
    r=SMCConfluenceEngine().analyze([]); assert r['bias']=='NEUTRAL'; assert r['score']==0

def test_custom_threshold_can_require_stronger_signal():
    r=SMCConfluenceEngine(ConfluenceWeights(threshold=999)).analyze(bars()); assert r['bias']=='NEUTRAL'
