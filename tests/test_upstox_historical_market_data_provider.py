from datetime import datetime, timezone

import pytest

from app.market_data.models import Instrument, Timeframe
from app.market_data.upstox import UpstoxHistoricalMarketDataProvider


class StubUpstoxAdapter:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_historical_candles(self, **kwargs):
        self.calls.append(kwargs)
        return list(self.rows)


@pytest.mark.asyncio
async def test_upstox_historical_rows_become_canonical_candles_and_are_deduped():
    adapter = StubUpstoxAdapter(
        [
            {
                "timestamp": "2026-08-31T09:16:00+05:30",
                "open": 101,
                "high": 105,
                "low": 100,
                "close": 104,
                "volume": 10,
            },
            {
                "timestamp": "2026-08-31T09:15:00+05:30",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 8,
            },
            {
                "timestamp": "2026-08-31T09:15:00+05:30",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 8,
            },
        ]
    )
    provider = UpstoxHistoricalMarketDataProvider(adapter)
    instrument = Instrument(symbol="NIFTY", exchange="NSE", instrument_token="NSE_INDEX|Nifty 50")
    start = datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)
    # Deliberately use an invalid range first to prove the boundary rejects it.
    with pytest.raises(ValueError, match="end must be >= start"):
        await provider.candles(instrument, Timeframe.FIVE_MINUTES, start, end)

    start = datetime(2026, 8, 31, 3, 45, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)
    candles = await provider.candles(instrument, Timeframe.FIVE_MINUTES, start, end)

    assert [c.timestamp for c in candles] == [
        datetime(2026, 8, 31, 3, 45, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 3, 46, tzinfo=timezone.utc),
    ]
    assert all(c.instrument == instrument for c in candles)
    assert all(c.timeframe == Timeframe.FIVE_MINUTES for c in candles)
    assert adapter.calls[0]["instrument_key"] == "NSE_INDEX|Nifty 50"
    assert adapter.calls[0]["unit"] == "minutes"
    assert adapter.calls[0]["interval"] == 5


@pytest.mark.asyncio
async def test_upstox_historical_provider_requires_instrument_token():
    provider = UpstoxHistoricalMarketDataProvider(StubUpstoxAdapter([]))
    instrument = Instrument(symbol="NIFTY", exchange="NSE")
    start = datetime(2026, 8, 31, 3, 45, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="instrument.instrument_token"):
        await provider.candles(instrument, Timeframe.ONE_MINUTE, start, end)
