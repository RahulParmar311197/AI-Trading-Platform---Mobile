from datetime import datetime, timezone

import pytest

from app.market_data import Candle, Instrument, Timeframe
from app.market_data.historical import load_historical_candles
from app.market_data.provider import HistoricalMarketDataProvider
from app.market_data.reconnect import ConnectionState, RealtimeConnectionState
from app.market_data.repository import HistoricalCandleRepository
from app.market_data.resync import MarketDataResynchronizer


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")
START = datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)
END = datetime(2026, 8, 31, 9, 16, tzinfo=timezone.utc)


class Provider(HistoricalMarketDataProvider):
    async def candles(self, instrument, timeframe, start, end):
        return [
            Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=START,
                open=100,
                high=102,
                low=99,
                close=101,
                volume=50,
            )
        ]


@pytest.mark.asyncio
async def test_resync_repairs_history_before_ready():
    repository = HistoricalCandleRepository()
    state = RealtimeConnectionState()
    resync = MarketDataResynchronizer(Provider(), repository, state)

    result = await resync.resync(
        INSTRUMENT,
        Timeframe.ONE_MINUTE,
        START,
        END,
        resume_sequence=200,
    )

    assert result.candles_loaded == 1
    assert result.ready is True
    assert repository.count() == 1
    assert state.snapshot(INSTRUMENT).state == ConnectionState.READY
    assert state.can_publish_to_strategy(INSTRUMENT) is True


@pytest.mark.asyncio
async def test_invalid_resync_range_fails_closed_without_loading():
    repository = HistoricalCandleRepository()
    state = RealtimeConnectionState()
    resync = MarketDataResynchronizer(Provider(), repository, state)

    with pytest.raises(ValueError):
        await resync.resync(INSTRUMENT, Timeframe.ONE_MINUTE, END, START, 1)
    assert repository.count() == 0
