from datetime import datetime,timedelta,timezone
from app.backtester import Backtester
from app.market_data import Candle

def candles(n=50):
 t=datetime(2026,1,1,tzinfo=timezone.utc); return [Candle('NIFTY','15m',t+timedelta(minutes=15*i),100+i,102+i,99+i,101+i,1000+i*5) for i in range(n)]

def test_short_history_returns_flat_metrics():
 r=Backtester().run(candles(10)); assert r.trades==0; assert r.total_return_pct==0

def test_backtest_returns_metrics():
 r=Backtester().run(candles()); assert r.initial_equity==1_000_000; assert r.final_equity>0; assert r.max_drawdown_pct>=0; assert r.win_rate_pct>=0
