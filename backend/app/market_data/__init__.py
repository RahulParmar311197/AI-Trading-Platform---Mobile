"""Canonical market-data contracts for the trading platform."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

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
    current = now or datetime.now(timezone.utc)
    current = current if current.tzinfo is not None else current.replace(tzinfo=timezone.utc)
    previous = None
    for candle in candles:
        if candle.instrument != first.instrument or candle.timeframe != first.timeframe:
            return False
        if candle.timestamp > current:
            return False
        if previous is not None and candle.timestamp <= previous:
            return False
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if not all(math.isfinite(float(value)) for value in values):
            return False
        if min(candle.open, candle.high, candle.low, candle.close) <= 0 or candle.volume < 0:
            return False
        previous = candle.timestamp
    return True


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    timestamp: datetime
    price: float
    volume: float = 0.0


_TIMEFRAME_RE = re.compile(r"^(\d+)([mhd])$")


def timeframe_seconds(timeframe: str) -> int:
    match = _TIMEFRAME_RE.fullmatch(timeframe.strip().lower())
    if not match:
        raise ValueError("unsupported timeframe; expected <number>m, <number>h, or <number>d")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("timeframe amount must be positive")
    seconds = amount * {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    if seconds > 86400 or 86400 % seconds != 0:
        raise ValueError("timeframe must divide one UTC day and be at most 1d")
    return seconds


class InMemoryMarketData:
    def __init__(self) -> None:
        self._candles: dict[tuple[str, str], list[Candle]] = {}
        self._last_tick: dict[str, datetime] = {}

    def put(self, candle: Candle) -> bool:
        if not validate_candle_sequence([candle]):
            raise ValueError("invalid candle")
        key = (candle.symbol, candle.timeframe.value)
        items = self._candles.setdefault(key, [])
        if items and candle.timestamp <= items[-1].timestamp:
            return False
        items.append(candle)
        self._candles[key] = items[-5000:]
        return True

    def ingest_tick(self, tick: MarketTick) -> bool:
        if not math.isfinite(float(tick.price)) or not math.isfinite(float(tick.volume)) or tick.price <= 0 or tick.volume < 0:
            raise ValueError("invalid market tick")
        symbol = tick.symbol.strip().upper()
        if not symbol:
            raise ValueError("tick symbol is required")
        if symbol in self._last_tick and tick.timestamp <= self._last_tick[symbol]:
            return False
        self._last_tick[symbol] = tick.timestamp
        return True

    def ingest_broker_candles(self, symbol: str, timeframe: str, rows: list[dict[str, Any]]) -> int:
        if not symbol.strip() or not timeframe.strip():
            raise ValueError("symbol and timeframe are required")
        normalized: list[Candle] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"invalid broker candle row at index {index}")
            timestamp = row.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"invalid broker candle timestamp at index {index}") from exc
            if not isinstance(timestamp, datetime):
                raise ValueError(f"invalid broker candle timestamp at index {index}")
            try:
                normalized.append(Candle(timestamp, symbol, timeframe, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row.get("volume", 0.0))))
            except Exception as exc:
                raise ValueError("broker candle batch failed canonical validation") from exc
        if not normalized:
            return 0
        # Preserve broker ordering so non-monotonic or future input cannot be
        # repaired by sorting into an apparently valid sequence.
        if not validate_candle_sequence(normalized):
            raise ValueError("broker candle batch failed canonical validation")
        return sum(1 for candle in normalized if self.put(candle))

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if limit <= 0:
            return []
        return list(self._candles.get((symbol.strip().upper(), timeframe.strip().lower()), []))[-limit:]


class TickCandleAggregator:
    def __init__(self) -> None:
        self._active: dict[tuple[str, str], Candle] = {}
        self._last_tick: dict[str, datetime] = {}

    def ingest(self, tick: MarketTick, timeframe: str) -> list[Candle]:
        if not isinstance(tick, MarketTick):
            raise TypeError("tick must be a MarketTick")
        if not math.isfinite(float(tick.price)) or not math.isfinite(float(tick.volume)) or tick.price <= 0 or tick.volume < 0:
            raise ValueError("invalid market tick")
        symbol = tick.symbol.strip().upper()
        if not symbol:
            raise ValueError("tick symbol is required")
        normalized = timeframe.strip().lower()
        seconds = timeframe_seconds(normalized)
        timestamp = tick.timestamp if tick.timestamp.tzinfo is not None else tick.timestamp.replace(tzinfo=timezone.utc)
        last = self._last_tick.get(symbol)
        if last is not None and timestamp <= last:
            return []
        self._last_tick[symbol] = timestamp
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        bucket = epoch + timedelta(seconds=int((timestamp - epoch).total_seconds()) // seconds * seconds)
        key = (symbol, normalized)
        active = self._active.get(key)
        if active is None:
            self._active[key] = Candle(bucket, symbol, normalized, tick.price, tick.price, tick.price, tick.price, tick.volume)
            return []
        if bucket == active.timestamp:
            self._active[key] = Candle(active.timestamp, symbol, normalized, active.open, max(active.high, tick.price), min(active.low, tick.price), tick.price, active.volume + tick.volume)
            return []
        if bucket < active.timestamp:
            return []
        finalized = active
        self._active[key] = Candle(bucket, symbol, normalized, tick.price, tick.price, tick.price, tick.price, tick.volume)
        return [finalized]

    def current(self, symbol: str, timeframe: str) -> Candle | None:
        return self._active.get((symbol.strip().upper(), timeframe.strip().lower()))

    def flush(self, symbol: str | None = None, timeframe: str | None = None) -> list[Candle]:
        symbol_key = symbol.strip().upper() if symbol is not None else None
        timeframe_key = timeframe.strip().lower() if timeframe is not None else None
        keys = [key for key in self._active if (symbol_key is None or key[0] == symbol_key) and (timeframe_key is None or key[1] == timeframe_key)]
        return [self._active.pop(key) for key in sorted(keys)]


market_data = InMemoryMarketData()

__all__ = [
    "Candle", "Instrument", "Tick", "Timeframe", "MarketTick", "HistoricalMarketDataProvider",
    "RealtimeMarketDataProvider", "MarketDataFreshness", "validate_freshness", "validate_candle_sequence",
    "MarketDataStore", "InMemoryMarketData", "TickCandleAggregator", "timeframe_seconds", "market_data",
]
MarketDataStore = InMemoryMarketData
