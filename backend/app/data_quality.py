from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from app.market_data import Candle
from app.market_calendar import NSEMarketCalendar
@dataclass(frozen=True)
class DataQualityIssue:
    code:str; message:str; timestamp:object|None=None
class CandleQualityValidator:
    def __init__(self,max_gap_multiplier:float=3.0,calendar:NSEMarketCalendar|None=None):
        if max_gap_multiplier<1: raise ValueError('max_gap_multiplier must be >= 1')
        self.max_gap_multiplier=max_gap_multiplier; self.calendar=calendar
    def validate(self,candles:list[Candle],expected_interval:timedelta|None=None)->list[DataQualityIssue]:
        issues=[]
        if not candles:return [DataQualityIssue('EMPTY_DATA','No candles supplied')]
        ordered=sorted(candles,key=lambda c:c.timestamp); seen=set(); previous=None
        for c in ordered:
            if c.timestamp in seen:issues.append(DataQualityIssue('DUPLICATE_TIMESTAMP','Duplicate candle timestamp',c.timestamp))
            seen.add(c.timestamp)
            if c.high<c.low or c.open<c.low or c.open>c.high or c.close<c.low or c.close>c.high:issues.append(DataQualityIssue('INVALID_OHLC','OHLC values violate candle bounds',c.timestamp))
            if c.volume<0:issues.append(DataQualityIssue('NEGATIVE_VOLUME','Volume cannot be negative',c.timestamp))
            if previous is not None:
                gap=c.timestamp-previous
                if gap.total_seconds()<=0:issues.append(DataQualityIssue('NON_MONOTONIC','Timestamps are not strictly increasing',c.timestamp))
                elif expected_interval:
                    large_gap=gap>expected_interval*self.max_gap_multiplier
                    if self.calendar: large_gap=self.calendar.expected_gap(previous,c.timestamp,expected_interval)
                    if large_gap:issues.append(DataQualityIssue('DATA_GAP','Unexpected trading-session candle gap',c.timestamp))
            previous=c.timestamp
        return issues
    def require_clean(self,candles:list[Candle],expected_interval:timedelta|None=None)->list[Candle]:
        issues=self.validate(candles,expected_interval)
        if issues:raise ValueError('; '.join(f'{x.code}: {x.message}' for x in issues))
        return sorted(candles,key=lambda c:c.timestamp)
