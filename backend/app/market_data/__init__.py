"""Canonical market-data contracts for the trading platform."""

from datetime import datetime, timezone

from .models import Candle, Instrument, Tick, Timeframe
from .provider import HistoricalMarketDataProvider, RealtimeMarketDataProvider


class MarketDataFreshness:
    __slots__ = ("fresh", "age_seconds", "max_age_seconds", "message")

    def __init__(self, fresh: bool, age_seconds: float, max_age_seconds: float, message: str = "") -> None:
        self.fresh = fresh
        self.age_seconds = age_seconds
        self.max_age_seconds = max_age_seconds
        self.message = message


def validate_freshness(
    timestamp: datetime,
    *,
    max_age_seconds: float,
    now: datetime | None = None,
) -> MarketDataFreshness:
    """Return a deterministic freshness decision; future data is never treated as fresh."""
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    current = now or datetime.now(timezone.utc)
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    current = current if current.tzinfo is not None else current.replace(tzinfo=timezone.utc)
    age = (current - ts).total_seconds()
    if age < 0:
        return MarketDataFreshness(False, age, max_age_seconds, "market-data timestamp is in the future")
    if age > max_age_seconds:
        return MarketDataFreshness(False, age, max_age_seconds, "market data is stale")
    return MarketDataFreshness(True, age, max_age_seconds, "ok")


def validate_candle_sequence(
    candles: list[Candle],
    *,
    now: datetime | None = None,
) -> bool:
    """Validate that a candle window is one instrument/timeframe with strict chronology."""
    if not candles:
        return False
    first = candles[0]
    current = now
    if current is not None:
        current = current if current.tzinfo is not None else current.replace(tzinfo=timezone.utc)
    previous = None
    for candle in candles:
        if candle.instrument != first.instrument or candle.timeframe != first.timeframe:
            return False
        timestamp = candle.timestamp
        if previous is not None and timestamp <= previous:
            return False
        if current is not None and timestamp > current:
            return False
        previous = timestamp
    return True


__all__ = [
    "Candle",
    "Instrument",
    "Tick",
    "Timeframe",
    "HistoricalMarketDataProvider",
    "RealtimeMarketDataProvider",
    "MarketDataFreshness",
    "validate_freshness",
    "validate_candle_sequence",
]
