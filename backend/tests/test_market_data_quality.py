from datetime import datetime, timedelta, timezone

import pytest

from app.market_context import Candle
from app.market_data_quality import assess_data_quality


def make_candles(n=50):
    start = datetime(2026, 8, 27, 9, 15, tzinfo=timezone.utc)
    return tuple(Candle(start + timedelta(minutes=i), 100, 101, 99, 100.5, 1000) for i in range(n))


def test_good_data():
    candles = make_candles()
    assert assess_data_quality(candles, as_of=candles[-1].timestamp).status == "GOOD"


def test_insufficient_history_is_degraded():
    candles = make_candles(10)
    assert assess_data_quality(candles, as_of=candles[-1].timestamp).status == "DEGRADED"


def test_duplicate_timestamp_is_invalid():
    candles = list(make_candles())
    candles[10] = candles[9]
    assert assess_data_quality(candles, as_of=candles[-1].timestamp).status == "INVALID"


def test_stale_data_is_stale():
    candles = make_candles()
    assert assess_data_quality(candles, as_of=candles[-1].timestamp + timedelta(minutes=11)).status == "STALE"


def test_future_latest_candle_is_stale():
    candles = make_candles()
    assert assess_data_quality(candles, as_of=candles[-1].timestamp - timedelta(minutes=2)).status == "STALE"
