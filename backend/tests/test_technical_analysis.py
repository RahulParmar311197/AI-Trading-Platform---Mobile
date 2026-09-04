from datetime import datetime, timedelta, timezone
import math

import pytest

from app.market_data import Candle
from app.technical_analysis import TechnicalAnalysisEngine


def candles(n=40):
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle('NIFTY', '15m', t + timedelta(minutes=15 * i), 100 + i, 102 + i, 99 + i, 101 + i, 1000 + i) for i in range(n)]


def test_snapshot_produces_core_indicators():
    s = TechnicalAnalysisEngine().snapshot(candles())
    assert s.ema_fast is not None
    assert s.ema_slow is not None
    assert s.rsi is not None
    assert s.macd is not None
    assert s.atr is not None
    assert s.adx is not None
    assert s.vwap is not None
    assert s.bollinger_upper is not None
    assert s.bollinger_middle is not None
    assert s.bollinger_lower is not None
    assert s.trend == 'BULLISH'


def test_invalid_ema_period_rejected():
    with pytest.raises(ValueError):
        TechnicalAnalysisEngine().ema([1, 2, 3], 0)


def test_snapshot_rejects_empty_input():
    with pytest.raises(ValueError, match='at least one canonical candle'):
        TechnicalAnalysisEngine().snapshot([])


def test_snapshot_rejects_non_monotonic_candles():
    items = candles(3)
    items[2] = Candle(items[0].timestamp, 'NIFTY', '15m', 102, 104, 101, 103, 1002)
    with pytest.raises(ValueError, match='invalid candle sequence'):
        TechnicalAnalysisEngine().snapshot(items)


def test_snapshot_rejects_mixed_symbol_or_timeframe():
    items = candles(3)
    items[1] = Candle(items[1].timestamp, 'BANKNIFTY', '15m', 101, 103, 100, 102, 1001)
    with pytest.raises(ValueError, match='invalid candle sequence'):
        TechnicalAnalysisEngine().snapshot(items)


def test_snapshot_rejects_non_finite_prices():
    items = candles(3)
    items[1] = Candle(items[1].timestamp, 'NIFTY', '15m', 101, 103, 100, math.nan, 1001)
    with pytest.raises(ValueError, match='invalid candle sequence'):
        TechnicalAnalysisEngine().snapshot(items)


def test_rsi_atr_adx_reject_invalid_periods():
    engine = TechnicalAnalysisEngine()
    with pytest.raises(ValueError):
        engine.rsi([1, 2, 3], 0)
    with pytest.raises(ValueError):
        engine.atr(candles(20), 0)
    with pytest.raises(ValueError):
        engine.adx(candles(20), 0)


def test_bollinger_rejects_invalid_multiplier():
    with pytest.raises(ValueError):
        TechnicalAnalysisEngine().bollinger([1, 2, 3], 2, -1)
    with pytest.raises(ValueError):
        TechnicalAnalysisEngine().bollinger([1, 2, 3], 2, math.nan)
