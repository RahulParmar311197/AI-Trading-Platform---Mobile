from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from typing import Callable
from app.mtf_aggregator import Candle
from app.historical_market_store import HistoricalMarketStore
@dataclass(frozen=True)
class BackfillGap:
    start:datetime
    end:datetime

def _utc(dt:datetime)->datetime:
    if dt.tzinfo is None: return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _key(value:datetime|str)->str:
    dt=datetime.fromisoformat(value) if isinstance(value,str) else value
    return _utc(dt).isoformat()
class HistoricalBackfillEngine:
    def __init__(self,store:HistoricalMarketStore,provider:Callable): self.store=store; self.provider=provider
    def find_gaps(self,symbol:str,timeframe:str,start:datetime,end:datetime,step_seconds:int):
        if step_seconds<=0: raise ValueError('step_seconds must be positive')
        start,end=_utc(start),_utc(end)
        if start>end: return []
        existing={_key(r['timestamp']) for r in self.store.query(symbol,timeframe,start,end,100000)}
        gaps=[]; cursor=start
        while cursor<=end:
            if _key(cursor) not in existing:
                gap_start=cursor
                while cursor<=end and _key(cursor) not in existing: cursor+=timedelta(seconds=step_seconds)
                gaps.append(BackfillGap(gap_start,min(end,cursor-timedelta(seconds=step_seconds))))
            else: cursor+=timedelta(seconds=step_seconds)
        return gaps
    def backfill(self,symbol:str,timeframe:str,start:datetime,end:datetime,step_seconds:int):
        gaps=self.find_gaps(symbol,timeframe,start,end,step_seconds); total=0
        for gap in gaps:
            raw=self.provider(symbol,timeframe,gap.start,gap.end)
            candles=[Candle(timestamp=_utc(x.timestamp),symbol=symbol.upper(),timeframe=timeframe,open=x.open,high=x.high,low=x.low,close=x.close,volume=x.volume) for x in raw]
            total+=self.store.upsert(candles)
        remaining=self.find_gaps(symbol,timeframe,start,end,step_seconds)
        return {'requested_gaps':len(gaps),'stored':total,'remaining_gaps':len(remaining),'complete':not remaining}
