from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from app.mtf_aggregator import Candle
from app.historical_market_store import HistoricalMarketStore
@dataclass(frozen=True)
class BackfillGap:
    start: datetime
    end: datetime
class HistoricalBackfillEngine:
    def __init__(self,store:HistoricalMarketStore,provider:Callable): self.store=store; self.provider=provider
    def find_gaps(self,symbol:str,timeframe:str,start:datetime,end:datetime,step_seconds:int):
        rows=self.store.query(symbol,timeframe,start,end,100000)
        if not rows:return [BackfillGap(start,end)]
        existing={r['timestamp'] for r in rows}; gaps=[]; cursor=start
        while cursor<=end:
            if cursor.isoformat() not in existing:
                gap_start=cursor
                while cursor<=end and cursor.isoformat() not in existing: cursor+=timedelta(seconds=step_seconds)
                gaps.append(BackfillGap(gap_start,min(end,cursor-timedelta(seconds=step_seconds))))
            cursor+=timedelta(seconds=step_seconds)
        return gaps
    def backfill(self,symbol:str,timeframe:str,start:datetime,end:datetime,step_seconds:int):
        gaps=self.find_gaps(symbol,timeframe,start,end,step_seconds); total=0
        for gap in gaps:
            raw=self.provider(symbol,timeframe,gap.start,gap.end)
            candles=[Candle(x.timestamp,x.open,x.high,x.low,x.close,x.volume,symbol,timeframe) for x in raw]
            total+=self.store.upsert(candles)
        remaining=self.find_gaps(symbol,timeframe,start,end,step_seconds)
        return {'requested_gaps':len(gaps),'stored':total,'remaining_gaps':len(remaining),'complete':not remaining}
