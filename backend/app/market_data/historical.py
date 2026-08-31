from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .models import Candle, Instrument, Timeframe
from .provider import HistoricalMarketDataProvider
from .repository import HistoricalCandleRepository


class RepositoryHistoricalMarketDataProvider(HistoricalMarketDataProvider):
    """Historical provider backed by the canonical candle repository.

    The adapter deliberately preserves the provider contract: inclusive UTC
    range semantics and deterministic chronological ordering are delegated to
    the repository rather than reimplemented by callers.
    """

    def __init__(self, repository: HistoricalCandleRepository):
        self._repository = repository

    async def candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]:
        return self._repository.get(instrument, timeframe, start, end)


async def load_historical_candles(
    provider: HistoricalMarketDataProvider,
    repository: HistoricalCandleRepository,
    instrument: Instrument,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    *,
    replace: bool = True,
) -> int:
    """Fetch a historical range and persist its canonical candles.

    Providers are expected to return normalized Candle objects. A repository
    upsert makes retries idempotent and protects callers from duplicate pages.
    """
    candles = await provider.candles(instrument, timeframe, start, end)
    if not replace:
        existing = {
            candle.timestamp
            for candle in repository.get(instrument, timeframe, start, end)
        }
        candles = [candle for candle in candles if candle.timestamp not in existing]
    return repository.upsert(candles)
