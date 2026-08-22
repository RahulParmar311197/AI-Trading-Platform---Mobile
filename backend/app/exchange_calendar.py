from __future__ import annotations
from abc import ABC,abstractmethod
from datetime import date,datetime,timedelta
from app.market_calendar import NSEMarketCalendar
class ExchangeCalendar(ABC):
 @abstractmethod
 def is_trading_day(self,d:date)->bool: ...
 @abstractmethod
 def is_session_time(self,dt:datetime)->bool: ...
 @abstractmethod
 def expected_gap(self,previous:datetime,current:datetime,interval:timedelta)->bool: ...
class BSEMarketCalendar(NSEMarketCalendar):
 """BSE equity calendar; holidays are supplied explicitly."""
class ExchangeCalendarRegistry:
 def __init__(self): self._calendars={'NSE':NSEMarketCalendar(),'BSE':BSEMarketCalendar()}
 def register(self,exchange:str,calendar:ExchangeCalendar):
  key=exchange.strip().upper()
  if not key: raise ValueError('exchange is required')
  self._calendars[key]=calendar
 def get(self,exchange:str)->ExchangeCalendar:
  key=exchange.strip().upper()
  if key not in self._calendars: raise ValueError(f'unsupported exchange: {exchange}')
  return self._calendars[key]
