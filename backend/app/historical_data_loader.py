from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from app.market_data import Candle
from app.data_quality import CandleQualityValidator
from app.timeframe import timeframe_interval
from app.exchange_calendar import ExchangeCalendarRegistry
@dataclass(frozen=True)
class HistoricalDataRequest:
 symbol:str; timeframe:str; start:datetime; end:datetime; exchange:str='NSE'; expected_interval:timedelta|None=None
class HistoricalDataLoader:
 def __init__(self,provider,quality_validator:CandleQualityValidator|None=None,calendar_registry:ExchangeCalendarRegistry|None=None): self.provider=provider; self.registry=calendar_registry or ExchangeCalendarRegistry(); self.validator=quality_validator
 def load(self,request:HistoricalDataRequest)->list[Candle]:
  if not request.symbol or request.start>=request.end: raise ValueError('invalid historical data request')
  if request.start.tzinfo is None or request.end.tzinfo is None: raise ValueError('timestamps must be timezone-aware')
  calendar=self.registry.get(request.exchange)
  validator=self.validator or CandleQualityValidator(calendar=calendar)
  candles=self.provider.fetch(request.symbol,request.timeframe,request.start,request.end)
  return validator.require_clean(candles,request.expected_interval or timeframe_interval(request.timeframe))
