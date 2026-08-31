from datetime import datetime, timedelta, timezone

import pytest

from app.market_data import Candle, Instrument, Timeframe
from app.market_data.repository import HistoricalCandleRepository


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")
BASE = datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc)


def candle(offset: int, close: float = 100) -> Candle:
    return Candle(
        instrument=INSTRUMENT,
        timeframe=Timeframe.ONE_MINUTE,
        timestamp=BASE + timedelta(minutes=offset),
        open=99,
        high=max(100, close),
        low=98,
        close=close,
        volume=10,
    )


def test_upsert_replaces_same_canonical_identity():
    repository = HistoricalCandleRepository()
    repository.upsert([candle(0, 100)])
    repository.upsert([candle(0, 105)])

    result = repository.get(INSTRUMENT, Timeframe.ONE_MINUTE, BASE, BASE)
    assert len(result) == 1
    assert result[0].close == 105
    assert repository.count() == 1


def test_range_query_is_sorted_and_inclusive():
    repository = HistoricalCandleRepository()
    repository.upsert([candle(2, 102), candle(0, 100), candle(1, 101)])

    result = repository.get(
        INSTRUMENT,
        Timeframe.ONE_MINUTE,
        BASE + timedelta(minutes=1),
        BASE + timedelta(minutes=2),
    )
    assert [item.close for item in result] == [101, 102]


def test_repository_isolated_by_instrument_and_timeframe():
    repository = HistoricalCandleRepository()
    repository.upsert([candle(0)])
    other = Candle(
        instrument=Instrument(symbol="INFY", exchange="NSE"),
        timeframe=Timeframe.FIVE_MINUTES,
        timestamp=BASE,
        open=1500,
        high=1510,
        low=1490,
        close=1505,
    )
    repository.upsert([other])

    assert len(repository.get(INSTRUMENT, Timeframe.ONE_MINUTE, BASE, BASE)) == 1
    assert len(repository.get(other.instrument, other.timeframe, BASE, BASE)) == 1


def test_rejects_naive_query_bounds_and_reversed_range():
    repository = HistoricalCandleRepository()
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.get(INSTRUMENT, Timeframe.ONE_MINUTE, datetime(2026, 8, 31, 9, 15), BASE)
    with pytest.raises(ValueError, match="end must be >= start"):
        repository.get(INSTRUMENT, Timeframe.ONE_MINUTE, BASE + timedelta(minutes=1), BASE)
