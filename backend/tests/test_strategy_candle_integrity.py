from datetime import datetime, timedelta, timezone

from app.market_data import Candle, validate_candle_sequence
from app.strategy import generate_signal


def candles(start, count=20, symbol="RELIANCE", timeframe="5m"):
    return [
        Candle(
            timestamp=start + timedelta(minutes=i),
            symbol=symbol,
            timeframe=timeframe,
            open=100 + i,
            high=102 + i,
            low=99 + i,
            close=101 + i,
            volume=1000,
        )
        for i in range(count)
    ]


def test_candle_sequence_rejects_mixed_symbol_and_timeframe():
    start = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(start)
    data[-1] = Candle(timestamp=data[-1].timestamp, symbol="TCS", timeframe="5m", open=119, high=121, low=118, close=120, volume=1000)
    assert not validate_candle_sequence(data, now=start + timedelta(minutes=20))

    data = candles(start)
    data[-1] = Candle(timestamp=data[-1].timestamp, symbol="RELIANCE", timeframe="15m", open=119, high=121, low=118, close=120, volume=1000)
    assert not validate_candle_sequence(data, now=start + timedelta(minutes=20))


def test_candle_sequence_rejects_out_of_order_and_future_data():
    start = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(start)
    data[10], data[11] = data[11], data[10]
    assert not validate_candle_sequence(data, now=start + timedelta(minutes=20))

    future = candles(start)
    future[-1] = Candle(timestamp=start + timedelta(hours=1), symbol="RELIANCE", timeframe="5m", open=119, high=121, low=118, close=120, volume=1000)
    assert not validate_candle_sequence(future, now=start + timedelta(minutes=20))


def test_strategy_rejects_malformed_series_even_without_freshness_gate():
    start = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(start)
    data[-1] = Candle(timestamp=data[-1].timestamp, symbol="RELIANCE", timeframe="5m", open=120, high=119, low=118, close=119, volume=1000)
    assert generate_signal(data, min_score=0, now=start + timedelta(minutes=20)) is None


def test_strategy_rejects_future_dated_series_without_freshness_gate():
    start = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(start)
    data[-1] = Candle(timestamp=start + timedelta(hours=1), symbol="RELIANCE", timeframe="5m", open=119, high=121, low=118, close=120, volume=1000)
    assert generate_signal(data, min_score=0, now=start + timedelta(minutes=20)) is None
