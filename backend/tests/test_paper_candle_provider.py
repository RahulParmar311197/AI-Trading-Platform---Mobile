from datetime import datetime, timedelta, timezone

import pytest

from app.market_context import Candle
from app.paper_candle_provider import PaperCandleProvider


def make_candles(n=5):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(Candle(start + timedelta(minutes=i), 100+i, 101+i, 99+i, 100.5+i, 1000+i) for i in range(n))


@pytest.mark.asyncio
async def test_latest_returns_tail_in_order():
    provider = PaperCandleProvider(make_candles())
    result = await provider.latest("NIFTY", interval="1m", limit=3)
    assert [c.close for c in result] == [102.5, 103.5, 104.5]


@pytest.mark.asyncio
async def test_historical_applies_time_range_and_limit():
    candles = make_candles()
    provider = PaperCandleProvider(candles)
    result = await provider.historical("NIFTY", interval="1m", start=candles[1].timestamp, end=candles[4].timestamp, limit=2)
    assert [c.close for c in result] == [103.5, 104.5]


@pytest.mark.asyncio
async def test_rejects_non_positive_limit():
    provider = PaperCandleProvider(make_candles())
    with pytest.raises(ValueError, match="positive"):
        await provider.latest("NIFTY", interval="1m", limit=0)
