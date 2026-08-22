from datetime import datetime,timezone,timedelta
from app.historical_data_loader import HistoricalDataLoader,HistoricalDataRequest
from app.market_data import Candle
class Provider:
 def fetch(self,symbol,timeframe,start,end):
  t=start; return [Candle(symbol,timeframe,t+timedelta(minutes=15),100,102,99,101,1000),Candle(symbol,timeframe,t,99,101,98,100,900)]
def test_loader_orders_candles():
 s=datetime(2026,1,1,tzinfo=timezone.utc); r=HistoricalDataLoader(Provider()).load(HistoricalDataRequest('NIFTY','15m',s,s+timedelta(hours=1))); assert r[0].timestamp<r[1].timestamp
def test_naive_timestamps_rejected():
 s=datetime(2026,1,1)
 try: HistoricalDataLoader(Provider()).load(HistoricalDataRequest('NIFTY','15m',s,s+timedelta(hours=1))); assert False
 except ValueError: pass
