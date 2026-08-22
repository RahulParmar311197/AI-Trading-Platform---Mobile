from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str

TIMEFRAME_SECONDS={"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1d":86400}

def _bucket(ts: datetime, seconds: int) -> datetime:
    epoch=int(ts.timestamp()); return datetime.fromtimestamp(epoch-(epoch%seconds),tz=ts.tzinfo)

class MultiTimeframeAggregator:
    def aggregate(self,candles:list[Candle],timeframe:str)->list[Candle]:
        if timeframe not in TIMEFRAME_SECONDS: raise ValueError("unsupported timeframe")
        if not candles:return []
        groups={}; seconds=TIMEFRAME_SECONDS[timeframe]
        for c in sorted(candles,key=lambda x:x.timestamp): groups.setdefault(_bucket(c.timestamp,seconds),[]).append(c)
        return [Candle(b,x[0].open,max(i.high for i in x),min(i.low for i in x),x[-1].close,sum(i.volume for i in x),x[0].symbol.upper(),timeframe) for b,x in groups.items()]
    def validate_alignment(self,candles:list[Candle],timeframe:str)->list[dict]:
        if timeframe not in TIMEFRAME_SECONDS: raise ValueError("unsupported timeframe")
        step=TIMEFRAME_SECONDS[timeframe]; issues=[]
        for c in candles:
            expected=_bucket(c.timestamp,step)
            if c.timestamp != expected: issues.append({"timestamp":c.timestamp.isoformat(),"expected_bucket":expected.isoformat()})
        return issues
