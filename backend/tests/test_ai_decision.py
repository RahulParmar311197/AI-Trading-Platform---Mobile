from datetime import datetime,timedelta,timezone
from app.market_data import Candle
from app.ai_decision import AIDecisionEngine

def bars(n=60):
 t=datetime(2026,1,1,tzinfo=timezone.utc); return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000+i*5) for i in range(n)]

def test_empty_market_waits():
 d=AIDecisionEngine().decide([]); assert d.action=='WAIT'; assert not d.tradeable

def test_invalid_confidence_rejected():
 try: AIDecisionEngine(1.1); assert False
 except ValueError: pass

def test_decision_has_explanation():
 d=AIDecisionEngine(0.0).decide(bars()); assert d.action in {'BUY','SELL','WAIT'}; assert isinstance(d.reasons,tuple)
