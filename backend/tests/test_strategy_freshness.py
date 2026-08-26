from datetime import datetime, timedelta, timezone

from app.market_data import Candle
from app.strategy import generate_signal


def candles(start, count=20):
    return [Candle(timestamp=start + timedelta(minutes=i), symbol="RELIANCE", timeframe="5m", open=100+i, high=102+i, low=99+i, close=101+i, volume=1000) for i in range(count)]


def test_stale_ltf_data_cannot_generate_signal():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(now - timedelta(minutes=30))
    assert generate_signal(data, min_score=0, max_age_seconds=60, now=now) is None


def test_fresh_ltf_data_preserves_signal_pipeline():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    data = candles(now - timedelta(seconds=5))
    result = generate_signal(data, min_score=999, max_age_seconds=60, now=now)
    assert result is None


def test_stale_htf_data_blocks_mtf_signal():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    ltf = candles(now - timedelta(seconds=5))
    htf = candles(now - timedelta(minutes=30))
    assert generate_signal(ltf, min_score=0, htf_candles=htf, max_age_seconds=60, now=now) is None
