from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import math
import re

from .models import Candle, Instrument, Tick, Timeframe


@dataclass(frozen=True)
class MarketDataFreshness:
    fresh: bool
    age_seconds: float
    max_age_seconds: float
    message: str = ""


def _utc(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


def validate_freshness(
    timestamp: datetime,
    *,
    max_age_seconds: float,
    now: datetime | None = None,
) -> MarketDataFreshness:
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    current = _utc(now or datetime.now(timezone.utc))
    ts = _utc(timestamp)
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
    """Reject malformed, mixed, out-of-order, or future-dated candle series."""
    if not candles:
        return False
    current = _utc(now or datetime.now(timezone.utc))
    first = candles[0]
    symbol = first.instrument.symbol.strip().upper()
    timeframe = first.timeframe
    if not symbol or timeframe is None:
        return False
    previous = None
    for candle in candles:
        if candle.instrument.symbol.strip().upper() != symbol or candle.timeframe != timeframe:
            return False
        timestamp = _utc(candle.timestamp)
        if timestamp > current:
            return False
        values = (float(candle.open), float(candle.high), float(candle.low), float(candle.close), float(candle.volume))
        if not all(math.isfinite(value) for value in values):
            return False
        opening, high, low, closing, volume = values
        if min(opening, high, low, closing) <= 0 or volume < 0:
            return False
        if high < max(opening, closing) or low > min(opening, closing):
            return False
        if previous is not None and timestamp <= previous:
            return False
        previous = timestamp
    return True


_TIMEFRAME_RE = re.compile(r"^(\d+)(m|h|d)$")


def timeframe_seconds(timeframe: str | Timeframe) -> int:
    value = timeframe.value if isinstance(timeframe, Timeframe) else timeframe.strip().lower()
    match = _TIMEFRAME_RE.fullmatch(value)
    if not match:
        raise ValueError("unsupported timeframe; expected <number>m, <number>h, or <number>d")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("timeframe amount must be positive")
    multiplier = {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    seconds = amount * multiplier
    if seconds > 86400 or 86400 % seconds != 0:
        raise ValueError("timeframe must divide one UTC day and be at most 1d")
    return seconds


def _bucket_start(timestamp: datetime, timeframe: Timeframe) -> datetime:
    ts = _utc(timestamp)
    seconds = timeframe_seconds(timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = int((ts - epoch).total_seconds())
    return epoch + timedelta(seconds=(elapsed // seconds) * seconds)


@dataclass
class _ActiveCandle:
    timestamp: datetime
    instrument: Instrument
    timeframe: Timeframe
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_candle(self) -> Candle:
        return Candle(
            timestamp=self.timestamp,
            instrument=self.instrument,
            timeframe=self.timeframe,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


class TickCandleAggregator:
    """Deterministic tick-to-candle aggregation using canonical market-data models."""

    def __init__(self):
        self._active: dict[tuple[str, Timeframe], _ActiveCandle] = {}
        self._last_tick: dict[str, datetime] = {}

    def ingest(self, tick: Tick, timeframe: Timeframe | str) -> list[Candle]:
        if not isinstance(tick, Tick):
            raise TypeError("tick must be a canonical Tick")
        if tick.price <= 0 or tick.volume < 0 or not math.isfinite(tick.price) or not math.isfinite(tick.volume):
            raise ValueError("invalid market tick")
        normalized_timeframe = Timeframe(timeframe)
        symbol = tick.instrument.symbol.strip().upper()
        timestamp = _utc(tick.timestamp)
        last = self._last_tick.get(symbol)
        if last is not None and timestamp <= last:
            return []
        self._last_tick[symbol] = timestamp
        key = (symbol, normalized_timeframe)
        bucket = _bucket_start(timestamp, normalized_timeframe)
        active = self._active.get(key)
        if active is None:
            self._active[key] = _ActiveCandle(bucket, tick.instrument, normalized_timeframe, tick.price, tick.price, tick.price, tick.price, tick.volume)
            return []
        if bucket == active.timestamp:
            active.high = max(active.high, tick.price)
            active.low = min(active.low, tick.price)
            active.close = tick.price
            active.volume += tick.volume
            return []
        if bucket < active.timestamp:
            return []
        finalized = active.to_candle()
        self._active[key] = _ActiveCandle(bucket, tick.instrument, normalized_timeframe, tick.price, tick.price, tick.price, tick.price, tick.volume)
        return [finalized]

    def current(self, instrument: Instrument | str, timeframe: Timeframe | str) -> Candle | None:
        symbol = instrument.symbol if isinstance(instrument, Instrument) else str(instrument)
        key = (symbol.strip().upper(), Timeframe(timeframe))
        active = self._active.get(key)
        return active.to_candle() if active else None

    def flush(self, instrument: Instrument | str | None = None, timeframe: Timeframe | str | None = None) -> list[Candle]:
        symbol_key = None
        if instrument is not None:
            symbol_key = instrument.symbol if isinstance(instrument, Instrument) else str(instrument)
            symbol_key = symbol_key.strip().upper()
        timeframe_key = Timeframe(timeframe) if timeframe is not None else None
        keys = [
            key for key in self._active
            if (symbol_key is None or key[0] == symbol_key)
            and (timeframe_key is None or key[1] == timeframe_key)
        ]
        finalized = [self._active.pop(key).to_candle() for key in sorted(keys, key=lambda item: (item[0], item[1].value))]
        return finalized


class InMemoryMarketData:
    """Validated deterministic candle/tick store for development and paper trading."""

    def __init__(self):
        self._candles: dict[tuple[str, Timeframe], list[Candle]] = {}
        self._last_tick: dict[str, datetime] = {}

    def put(self, candle: Candle) -> bool:
        key = (candle.instrument.symbol, candle.timeframe)
        items = self._candles.setdefault(key, [])
        if items and candle.timestamp <= items[-1].timestamp:
            return False
        items.append(candle)
        self._candles[key] = items[-5000:]
        return True

    def ingest_tick(self, tick: Tick) -> bool:
        symbol = tick.instrument.symbol
        if symbol in self._last_tick and tick.timestamp <= self._last_tick[symbol]:
            return False
        self._last_tick[symbol] = tick.timestamp
        return True

    def ingest_broker_candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        rows: list[Mapping[str, Any]],
    ) -> int:
        normalized: list[Candle] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
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
                normalized.append(
                    Candle(
                        timestamp=_utc(timestamp),
                        instrument=instrument,
                        timeframe=timeframe,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid broker candle row at index {index}") from exc
        normalized.sort(key=lambda candle: candle.timestamp)
        if not normalized:
            return 0
        if not validate_candle_sequence(normalized):
            raise ValueError("broker candle batch failed canonical validation")
        return sum(1 for candle in normalized if self.put(candle))

    def candles(self, instrument: Instrument, timeframe: Timeframe, limit: int = 200) -> list[Candle]:
        if limit <= 0:
            return []
        return self._candles.get((instrument.symbol, timeframe), [])[-limit:]
