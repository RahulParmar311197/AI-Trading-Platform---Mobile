from datetime import datetime, timezone

import pytest

from app.market_data import Candle, Instrument, Timeframe
from app.market_data.historical import RepositoryHistoricalMarketDataProvider, load_historical_candles
from app.market_data.repository import HistoricalCandleRepository
from app.market_data.provider import HistoricalMarketDataProvider


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")
START = datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)
END = datetime(2026, 8, 31, 9, 20, tzinfo=timezone.utc)


def candle(minute: int, close: float) -> Candle:
    return Candle(
        instrument=INSTRUMENT,
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=datetime(2026, 8, 31, 9, minute, tzinfo=timezone.utc),
        open=100,
        high=max(100, close),
        low=min(100, close),
        close=close,
        volume=10,
    )


class FixtureProvider(HistoricalMarketDataProvider):
    async def candles(self, instrument, timeframe, start, end):
        return [candle(17, 102), candle(15, 100), candle(16, 101)]


@pytest.mark.asyncio
async def test_repository_provider_returns_deterministic_range():
    repository = HistoricalCandleRepository()
    repository.upsert([candle(17, 102), candle(15, 100), candle(16, 101)])
    provider = RepositoryHistoricalMarketDataProvider(repository)

    result = await provider.candles(INSTRUMENT, Timeframe.ONE_MINUTE, START, END)

    assert [item.timestamp.minute for item in result] == [15, 16, 17]


@pytest.mark.asyncio
async def test_load_is_idempotent_on_retry():
    repository = HistoricalCandleRepository()
    provider = FixtureProvider()

    assert await load_historical_candles(provider, repository, INSTRUMENT, Timeframe.ONE_MINUTE, START, END) == 3
    assert await load_historical_candles(provider, repository, INSTRUMENT, Timeframe.ONE_MINUTE, START, END) == 3
    assert repository.count() == 3


@pytest.mark.asyncio
async def test_load_without_replace_does_not_duplicate_existing_range():
    repository = HistoricalCandleRepository()
    provider = FixtureProvider()
    repository.upsert([candle(15, 100)])

    written = await load_historical_candles(
        provider, repository, INSTRUMENT, Timeframe.ONE_MINUTE, START, END, replace=False
    )

    assert written == 2
    assert repository.count() == 3
