from datetime import datetime, timedelta, timezone

import pytest

from app.market_data import validate_freshness


def test_fresh_timestamp_is_accepted():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    result = validate_freshness(now - timedelta(seconds=2), max_age_seconds=5, now=now)
    assert result.fresh is True
    assert result.age_seconds == 2


def test_stale_timestamp_is_rejected():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    result = validate_freshness(now - timedelta(seconds=6), max_age_seconds=5, now=now)
    assert result.fresh is False
    assert result.message == "market data is stale"


def test_future_timestamp_is_rejected():
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    result = validate_freshness(now + timedelta(seconds=1), max_age_seconds=5, now=now)
    assert result.fresh is False
    assert "future" in result.message


def test_naive_timestamps_are_treated_as_utc():
    now = datetime(2026, 8, 26, 10, 0)
    result = validate_freshness(now - timedelta(seconds=1), max_age_seconds=5, now=now)
    assert result.fresh is True


def test_negative_max_age_is_invalid():
    with pytest.raises(ValueError):
        validate_freshness(datetime.now(timezone.utc), max_age_seconds=-1)
