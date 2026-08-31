from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from datetime import datetime

from .models import Candle, Instrument, Tick, Timeframe


class HistoricalMarketDataProvider(ABC):
    """Provider contract for deterministic historical candle retrieval."""

    @abstractmethod
    async def candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]:
        raise NotImplementedError


class RealtimeMarketDataProvider(ABC):
    """Provider contract for normalized realtime ticks."""

    @abstractmethod
    def ticks(self, instruments: Sequence[Instrument]) -> AsyncIterator[Tick]:
        raise NotImplementedError
