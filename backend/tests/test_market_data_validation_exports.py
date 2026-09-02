from datetime import datetime, timedelta, timezone

from app.market_data import Candle, Instrument, Timeframe, validate_candle_sequence, validate_freshness


def _candle(instrument, timestamp, close=100.0):
    return Candle(
        instrument=instrument,
        timeframe=Timeframe.FIVE_MINUTES,
        timestamp=timestamp,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
    )


def test_strategy_market_data_validation_exports_are_importable():
    instrument = Instrument(symbol="NIFTY", exchange="NSE")
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    candles = [_candle(instrument, now - timedelta(minutes=10)), _candle(instrument, now)]

    assert validate_candle_sequence(candles, now=now)
    freshness = validate_freshness(candles[-1].timestamp, max_age_seconds=0, now=now)
    assert freshness.fresh


def test_candle_sequence_rejects_mixed_identity_and_non_monotonic_timestamps():
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    first = Instrument(symbol="NIFTY", exchange="NSE")
    second = Instrument(symbol="BANKNIFTY", exchange="NSE")

    assert not validate_candle_sequence(
        [_candle(first, now - timedelta(minutes=5)), _candle(second, now)], now=now
    )
    assert not validate_candle_sequence(
        [_candle(first, now), _candle(first, now)], now=now
    )


def test_candle_sequence_rejects_future_timestamp():
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    instrument = Instrument(symbol="NIFTY", exchange="NSE")

    assert not validate_candle_sequence([_candle(instrument, now + timedelta(seconds=1))], now=now)


def test_freshness_rejects_future_and_stale_data():
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

    future = validate_freshness(now + timedelta(seconds=1), max_age_seconds=30, now=now)
    stale = validate_freshness(now - timedelta(seconds=31), max_age_seconds=30, now=now)

    assert not future.fresh
    assert "future" in future.message
    assert not stale.fresh
    assert stale.message == "market data is stale"
