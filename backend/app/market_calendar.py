from __future__ import annotations
from dataclasses import dataclass
from datetime import date,time,datetime,timedelta
from zoneinfo import ZoneInfo
@dataclass(frozen=True)
class Session:
    open_time:time=time(9,15); close_time:time=time(15,30)
class NSEMarketCalendar:
    def __init__(self,holidays:set[date]|None=None,tz:str='Asia/Kolkata'):
        self.holidays=holidays or set(); self.tz=ZoneInfo(tz); self.session=Session()
    def is_trading_day(self,d:date)->bool:return d.weekday()<5 and d not in self.holidays
    def is_session_time(self,dt:datetime)->bool:
        local=dt.astimezone(self.tz); return self.is_trading_day(local.date()) and self.session.open_time<=local.time().replace(tzinfo=None)<=self.session.close_time
    def expected_gap(self,previous:datetime,current:datetime,interval:timedelta)->bool:
        if current<=previous:return True
        p=previous.astimezone(self.tz); c=current.astimezone(self.tz)
        if p.date()==c.date(): return current-previous>interval*3
        d=p.date()+timedelta(days=1)
        while d<c.date():
            if self.is_trading_day(d): return True
            d+=timedelta(days=1)
        return False
