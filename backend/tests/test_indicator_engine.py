from datetime import datetime, timedelta, timezone

from app.indicator_engine import calculate_indicators
from app.market_context import Candle


def candles(n=60):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(Candle(start + timedelta(minutes=i), 100+i, 101+i, 99+i, 100.5+i, 1000) for i in range(n))


def test_calculates_canonical_indicators_with_sufficient_history():
    snapshot = calculate_indicators(candles())
    values = snapshot.values
    assert values["ema_20"] is not None
    assert values["ema_50"] is not None
    assert values["rsi_14"] == 100.0
    assert values["atr_14"] is not None
    assert values["adx_14"] is not None
    assert values["macd_histogram"] is not None


def test_returns_missing_values_when_history_is_insufficient():
    values = calculate_indicators(candles(10)).values
    assert values["ema_20"] is None
    assert values["ema_50"] is None
    assert values["rsi_14"] is None
    assert values["atr_14"] is None
    assert values["adx_14"] is None
    assert values["macd_histogram"] is None
