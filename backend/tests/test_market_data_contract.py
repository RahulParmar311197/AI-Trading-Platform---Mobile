from datetime import datetime, timedelta, timezone
import math

import pytest

from app.market_data import Candle, Instrument, validate_candle_sequence, validate_freshness, timeframe_seconds


def _candle(ts: datetime, *, symbol: str = "NIFTY", timeframe: str = "5m", close: float = 101.0) -> Candle:
    return Candle(ts, symbol, timeframe, 100.0, 102.0, 99.0, close, 1000.0)


def test_validate_freshness_fails_closed_for_future_and_stale_data():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    future = validate_freshness(now + timedelta(seconds=1), max_age_seconds=30, now=now)
    stale = validate_freshness(now - timedelta(seconds=31), max_age_seconds=30, now=now)

    assert future.fresh is False
    assert "future" in future.message
    assert stale.fresh is False
    assert stale.message == "market data is stale"


def test_validate_freshness_accepts_data_within_bound():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    result = validate_freshness(now - timedelta(seconds=30), max_age_seconds=30, now=now)

    assert result.fresh is True
    assert result.age_seconds == 30
    assert result.message == "ok"


def test_validate_candle_sequence_rejects_mixed_identity_and_non_monotonic_time():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    assert not validate_candle_sequence([
        _candle(now - timedelta(minutes=10)),
        _candle(now - timedelta(minutes=5), symbol="BANKNIFTY"),
    ], now=now)
    assert not validate_candle_sequence([
        _candle(now - timedelta(minutes=5)),
        _candle(now - timedelta(minutes=10)),
    ], now=now)


def test_validate_candle_sequence_rejects_invalid_numeric_ohlcv():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    invalid = Candle.model_construct(
        instrument=Instrument(symbol="NIFTY", exchange="UNKNOWN"),
        timeframe="5m",
        timestamp=now - timedelta(minutes=5),
        open=100.0,
        high=102.0,
        low=99.0,
        close=math.nan,
        volume=1000.0,
    )
    assert not validate_candle_sequence([invalid], now=now)


def test_validate_candle_sequence_rejects_future_candles():
    now = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    assert not validate_candle_sequence([_candle(now + timedelta(seconds=1))], now=now)


def test_timeframe_seconds_rejects_unsupported_bucket_widths():
    with pytest.raises(ValueError):
        timeframe_seconds("7m")
    with pytest.raises(ValueError):
        timeframe_seconds("25h")
    with pytest.raises(ValueError):
        timeframe_seconds("1w")
