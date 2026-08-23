from datetime import datetime,timedelta,timezone
from app.backtest_runner import BacktestRunner,BacktestRunRequest
from app.market_data import Candle
class Provider:
 def fetch(self,symbol,timeframe,start,end):
  return [Candle(symbol,timeframe,start+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000) for i in range(80)]
def test_end_to_end_runner():
 s=datetime(2026,1,1,tzinfo=timezone.utc); r=BacktestRunner(Provider()).run(BacktestRunRequest('NIFTY','15m',s,s+timedelta(days=1),100000)); assert r.analytics.initial_equity==100000; assert len(r.equity_curve)>1
