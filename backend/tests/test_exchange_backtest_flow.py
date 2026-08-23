from datetime import datetime,timezone
from app.exchange_calendar import ExchangeCalendarRegistry
from app.historical_data_loader import HistoricalDataLoader,HistoricalDataRequest
from app.market_data import Candle
class Provider:
 def fetch(self,symbol,timeframe,start,end): return [Candle(symbol,timeframe,start,100,102,99,101,1000)]
def test_registry_has_nse_and_bse():
 r=ExchangeCalendarRegistry(); assert r.get('NSE') is not None; assert r.get('bse') is not None
def test_loader_uses_requested_exchange():
 s=datetime(2026,1,2,9,15,tzinfo=timezone.utc); rows=HistoricalDataLoader(Provider()).load(HistoricalDataRequest('NIFTY','15m',s,s.replace(hour=10),exchange='BSE')); assert len(rows)==1
def test_unsupported_exchange_fails():
 r=ExchangeCalendarRegistry()
 try:r.get('NYSE'); assert False
 except ValueError as e:assert 'unsupported exchange' in str(e)
