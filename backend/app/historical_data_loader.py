from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.market_data import Candle
from app.data_quality import CandleQualityValidator
from app.timeframe import timeframe_interval
@dataclass(frozen=True)
class HistoricalDataRequest:
    symbol:str; timeframe:str; start:datetime; end:datetime; expected_interval:timedelta|None=None
class HistoricalDataLoader:
    """Provider-agnostic loader with mandatory candle quality validation."""
    def __init__(self,provider,quality_validator:CandleQualityValidator|None=None): self.provider=provider; self.validator=quality_validator or CandleQualityValidator()
    def load(self,request:HistoricalDataRequest)->list[Candle]:
        if not request.symbol or request.start>=request.end: raise ValueError('invalid historical data request')
        if request.start.tzinfo is None or request.end.tzinfo is None: raise ValueError('timestamps must be timezone-aware')
        candles=self.provider.fetch(request.symbol,request.timeframe,request.start,request.end)
        interval=request.expected_interval or timeframe_interval(request.timeframe)
        return self.validator.require_clean(candles,interval)
