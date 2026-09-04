"""Canonical market-data contracts for the trading platform."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import Candle, Instrument, Tick, Timeframe
from .provider import HistoricalMarketDataProvider, RealtimeMarketDataProvider


@dataclass(frozen=True)
class MarketDataFreshness:
    fresh: bool
    age_seconds: float
    max_age_seconds: float
    message: str = ""


def validate_freshness(timestamp: datetime, *, max_age_seconds: float, now: datetime | None = None) -> MarketDataFreshness:
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


def validate_candle_sequence(candles: list[Candle], *, now: datetime | None = None) -> bool:
    if not candles:
        return False
    first = candles[0]
    current = now if now is None or now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
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


class MarketDataStore:
    """Small in-process canonical store used by API development and tests."""
    def __init__(self) -> None:
        self._candles: dict[tuple[str, Timeframe], list[Candle]] = {}

    def put(self, candle: Candle) -> bool:
        key = (candle.instrument.symbol, candle.timeframe)
        items = self._candles.setdefault(key, [])
        if items and candle.timestamp <= items[-1].timestamp:
            return False
        items.append(candle)
        self._candles[key] = items[-5000:]
        return True

    def candles(self, symbol: str, timeframe: str = "5m", limit: int = 200) -> list[Candle]:
        if limit <= 0:
            return []
        try:
            tf = Timeframe(timeframe.strip().lower())
        except ValueError:
            return []
        return list(self._candles.get((symbol.strip().upper(), tf), []))[-limit:]


market_data = MarketDataStore()


__all__ = [
    "Candle", "Instrument", "Tick", "Timeframe", "HistoricalMarketDataProvider",
    "RealtimeMarketDataProvider", "MarketDataFreshness", "validate_freshness",
    "validate_candle_sequence", "MarketDataStore", "market_data",
]
