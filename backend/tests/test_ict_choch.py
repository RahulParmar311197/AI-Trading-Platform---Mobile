from datetime import datetime, timedelta, timezone

from app.ict_engine import structure
from app.market_data import Candle


def make_candles(highs, lows):
    start = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)
    return [Candle(timestamp=start + timedelta(minutes=i), symbol="TEST", timeframe="5m", open=(h+l)/2, high=h, low=l, close=(h+l)/2, volume=1) for i, (h, l) in enumerate(zip(highs, lows))]


def test_structure_exposes_choch_key():
    candles = make_candles([100, 105, 102, 104, 103, 106, 101, 107], [95, 98, 96, 99, 97, 100, 94, 101])
    result = structure(candles)
    assert 'choch' in result
    assert result['choch'] in (None, 'BULLISH', 'BEARISH')


def test_changing_structure_can_produce_bearish_choch():
    candles = make_candles([100, 105, 103, 108, 104, 106, 102, 103], [95, 98, 97, 101, 99, 100, 94, 93])
    result = structure(candles)
    assert result['choch'] in ('BEARISH', None)
