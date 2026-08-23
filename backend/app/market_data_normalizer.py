from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Candle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str

class MarketDataNormalizer:
    REQUIRED=("timestamp","open","high","low","close","volume")
    def normalize(self, raw: dict, symbol: str, timeframe: str) -> Candle:
        missing=[x for x in self.REQUIRED if x not in raw]
        if missing: raise ValueError(f"missing fields: {','.join(missing)}")
        ts=raw["timestamp"]
        if isinstance(ts,str): ts=datetime.fromisoformat(ts.replace("Z","+00:00"))
        o,h,l,c,v=map(float,(raw["open"],raw["high"],raw["low"],raw["close"],raw["volume"]))
        if min(o,h,l,c,v)<0 or h < max(o,c) or l > min(o,c) or h < l: raise ValueError("invalid OHLCV candle")
        return Candle(symbol.upper(),ts,o,h,l,c,v,timeframe)

class GapDetector:
    def detect(self, candles: list[Candle], expected_seconds: int) -> list[dict]:
        items=sorted(candles,key=lambda x:x.timestamp); gaps=[]
        for a,b in zip(items,items[1:]):
            seconds=(b.timestamp-a.timestamp).total_seconds()
            if seconds > expected_seconds*1.5: gaps.append({"from":a.timestamp.isoformat(),"to":b.timestamp.isoformat(),"missing_seconds":seconds-expected_seconds})
        return gaps
