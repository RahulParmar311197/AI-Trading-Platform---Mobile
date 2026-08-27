from datetime import datetime, timezone

import pytest

from app.candle_provider import normalize_candle, normalize_candles
from app.market_context import Candle


def ts():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_normalizes_mapping():
    candle = normalize_candle({"timestamp": ts(), "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000})
    assert isinstance(candle, Candle)
    assert candle.close == 103.0


def test_normalizes_sequence():
    candle = normalize_candle((ts(), 100, 105, 99, 103, 1000))
    assert candle.open == 100.0
    assert candle.volume == 1000.0


def test_preserves_canonical_candle():
    candle = Candle(ts(), 100, 105, 99, 103, 1000)
    assert normalize_candle(candle) is candle


def test_rejects_invalid_sequence_shape():
    with pytest.raises(ValueError, match="six|6"):
        normalize_candle((ts(), 100, 105))


def test_normalizes_collection():
    result = normalize_candles([
        {"timestamp": ts(), "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
    ])
    assert len(result) == 1
    assert isinstance(result[0], Candle)
