from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
@dataclass(frozen=True)
class Candle:
    timestamp:datetime; open:float; high:float; low:float; close:float; volume:float; symbol:str; timeframe:str
TIMEFRAME_SECONDS={"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1d":86400}
def _utc(ts:datetime)->datetime:
    if ts.tzinfo is None:return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
def _bucket(ts:datetime,seconds:int)->datetime:
    ts=_utc(ts); epoch=int(ts.timestamp()); return datetime.fromtimestamp(epoch-(epoch%seconds),tz=timezone.utc)
class MultiTimeframeAggregator:
    def aggregate(self,candles:list[Candle],timeframe:str)->list[Candle]:
        if timeframe not in TIMEFRAME_SECONDS:raise ValueError("unsupported timeframe")
        if not candles:return []
        seconds=TIMEFRAME_SECONDS[timeframe]; groups={}
        for c in sorted(candles,key=lambda x:_utc(x.timestamp)):
            groups.setdefault(_bucket(c.timestamp,seconds),[]).append(c)
        return [Candle(b,x[0].open,max(i.high for i in x),min(i.low for i in x),x[-1].close,sum(i.volume for i in x),x[0].symbol.upper(),timeframe) for b,x in groups.items()]
    def validate_alignment(self,candles:list[Candle],timeframe:str)->list[dict]:
        if timeframe not in TIMEFRAME_SECONDS:raise ValueError("unsupported timeframe")
        step=TIMEFRAME_SECONDS[timeframe]; issues=[]
        for c in candles:
            expected=_bucket(c.timestamp,step)
            if _utc(c.timestamp)!=expected:issues.append({"timestamp":_utc(c.timestamp).isoformat(),"expected_bucket":expected.isoformat()})
        return issues
