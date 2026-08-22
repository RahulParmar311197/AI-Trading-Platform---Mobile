from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.market_data import Candle

@dataclass(frozen=True)
class HistoricalDataRequest:
    symbol:str; timeframe:str; start:datetime; end:datetime

class HistoricalDataLoader:
    """Provider-agnostic historical candle loader."""
    def __init__(self,provider): self.provider=provider
    def load(self,request:HistoricalDataRequest)->list[Candle]:
        if not request.symbol or request.start>=request.end: raise ValueError('invalid historical data request')
        if request.start.tzinfo is None or request.end.tzinfo is None: raise ValueError('timestamps must be timezone-aware')
        candles=self.provider.fetch(request.symbol,request.timeframe,request.start,request.end)
        ordered=sorted(candles,key=lambda c:c.timestamp)
        if any(ordered[i].timestamp>=ordered[i+1].timestamp for i in range(len(ordered)-1)): raise ValueError('historical candles must be strictly increasing')
        return ordered
