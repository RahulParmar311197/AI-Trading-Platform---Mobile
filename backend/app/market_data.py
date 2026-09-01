from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Protocol
import math
import re


@dataclass(frozen=True, init=False)
class Candle:
    """OHLCV candle supporting all constructor orders used by the merged codebase."""
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __init__(self, *args, **kwargs):
        fields = ("timestamp", "symbol", "timeframe", "open", "high", "low", "close", "volume")
        values = dict(kwargs)
        if args:
            if len(args) > len(fields):
                raise TypeError(f"Candle expected at most {len(fields)} positional arguments")
            if isinstance(args[0], str) and len(args) >= 3 and isinstance(args[2], datetime):
                positional_fields = ("symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume")
            elif isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], datetime):
                if len(args) >= 3 and not isinstance(args[2], str):
                    positional_fields = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
                else:
                    positional_fields = ("symbol", "timestamp", "timeframe", "open", "high", "low", "close", "volume")
            else:
                positional_fields = fields
            for name, value in zip(positional_fields, args):
                if name in values:
                    raise TypeError(f"Candle got multiple values for argument '{name}'")
                values[name] = value
        values.setdefault("timeframe", "5m")
        required = ("timestamp", "symbol", "open", "high", "low", "close")
        missing = [name for name in required if name not in values]
        if missing:
            raise TypeError(f"Candle missing required arguments: {', '.join(missing)}")
        values.setdefault("volume", 0.0)
        for name in fields:
            object.__setattr__(self, name, values[name])


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    timestamp: datetime
    price: float
    volume: float = 0.0


@dataclass(frozen=True)
class MarketDataFreshness:
    fresh: bool
    age_seconds: float
    max_age_seconds: float
    message: str = ""


def _utc(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


def validate_freshness(timestamp: datetime, *, max_age_seconds: float, now: datetime | None = None) -> MarketDataFreshness:
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


def validate_candle_sequence(candles: list[Candle], *, now: datetime | None = None) -> bool:
    """Reject malformed, mixed, out-of-order, or future-dated candle series before indicators run."""
    if not candles:
        return False
    current = _utc(now or datetime.now(timezone.utc))
    first = candles[0]
    symbol = str(first.symbol).strip().upper()
    timeframe = str(first.timeframe).strip()
    if not symbol or not timeframe:
        return False
    previous = None
    for candle in candles:
        if str(candle.symbol).strip().upper() != symbol or str(candle.timeframe).strip() != timeframe:
            return False
        timestamp = _utc(candle.timestamp)
        if timestamp > current:
            return False
        try:
            values = (float(candle.open), float(candle.high), float(candle.low), float(candle.close), float(candle.volume))
        except (TypeError, ValueError):
            return False
        if not all(math.isfinite(value) for value in values):
            return False
        open_price, high, low, close, volume = values
        if min(open_price, high, low, close) <= 0 or volume < 0:
            return False
        if high < max(open_price, close) or low > min(open_price, close):
            return False
        if previous is not None and timestamp <= previous:
            return False
        previous = timestamp
    return True


class MarketDataProvider(Protocol):
    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]: ...


_TIMEFRAME_RE = re.compile(r"^(\d+)([mhd])$")


def timeframe_seconds(timeframe: str) -> int:
    """Return the fixed UTC bucket width for a supported intraday timeframe."""
    match = _TIMEFRAME_RE.fullmatch(timeframe.strip().lower())
    if not match:
        raise ValueError("unsupported timeframe; expected <number>m, <number>h, or <number>d")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("timeframe amount must be positive")
    unit = match.group(2)
    multiplier = {"m": 60, "h": 3600, "d": 86400}[unit]
    seconds = amount * multiplier
    if seconds > 86400 or 86400 % seconds != 0:
        raise ValueError("timeframe must divide one UTC day and be at most 1d")
    return seconds


def _bucket_start(timestamp: datetime, timeframe: str) -> datetime:
    ts = _utc(timestamp)
    seconds = timeframe_seconds(timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = int((ts - epoch).total_seconds())
    return epoch + timedelta(seconds=(elapsed // seconds) * seconds)


@dataclass
class _ActiveCandle:
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_candle(self) -> Candle:
        return Candle(
            timestamp=self.timestamp,
            symbol=self.symbol,
            timeframe=self.timeframe,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


class TickCandleAggregator:
    """Deterministic tick-to-candle aggregation using the canonical Candle contract.

    Ticks must be strictly increasing per symbol. A new bucket finalizes the previous
    bucket; gaps are intentionally not filled with synthetic candles.
    """
    def __init__(self):
        self._active: dict[tuple[str, str], _ActiveCandle] = {}
        self._last_tick: dict[str, datetime] = {}

    def ingest(self, tick: MarketTick, timeframe: str) -> list[Candle]:
        if not isinstance(tick, MarketTick):
            raise TypeError("tick must be a MarketTick")
        if tick.price <= 0 or tick.volume < 0 or not math.isfinite(tick.price) or not math.isfinite(tick.volume):
            raise ValueError("invalid market tick")
        seconds = timeframe_seconds(timeframe)
        normalized_timeframe = timeframe.strip().lower()
        symbol = tick.symbol.strip().upper()
        if not symbol:
            raise ValueError("tick symbol is required")
        timestamp = _utc(tick.timestamp)
        last = self._last_tick.get(symbol)
        if last is not None and timestamp <= last:
            return []
        self._last_tick[symbol] = timestamp
        key = (symbol, normalized_timeframe)
        bucket = _bucket_start(timestamp, normalized_timeframe)
        active = self._active.get(key)
        if active is None:
            self._active[key] = _ActiveCandle(bucket, symbol, normalized_timeframe, tick.price, tick.price, tick.price, tick.price, tick.volume)
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
        if bucket - active.timestamp < timedelta(seconds=seconds):
            # A bucket transition is always exactly the next bucket for fixed widths;
            # this branch is retained as an invariant guard.
            raise RuntimeError("invalid candle bucket transition")
        self._active[key] = _ActiveCandle(bucket, symbol, normalized_timeframe, tick.price, tick.price, tick.price, tick.price, tick.volume)
        return [finalized]

    def current(self, symbol: str, timeframe: str) -> Candle | None:
        active = self._active.get((symbol.strip().upper(), timeframe.strip().lower()))
        return active.to_candle() if active else None

    def flush(self, symbol: str | None = None, timeframe: str | None = None) -> list[Candle]:
        """Finalize active buckets explicitly; never manufacture missing candles."""
        symbol_key = symbol.strip().upper() if symbol is not None else None
        timeframe_key = timeframe.strip().lower() if timeframe is not None else None
        keys = [key for key in self._active if (symbol_key is None or key[0] == symbol_key) and (timeframe_key is None or key[1] == timeframe_key)]
        finalized = [self._active.pop(key).to_candle() for key in sorted(keys)]
        return finalized


class InMemoryMarketData:
    """Validated deterministic provider for development, tests and paper trading."""
    def __init__(self):
        self._candles: dict[tuple[str, str], list[Candle]] = {}
        self._last_tick: dict[str, datetime] = {}

    def put(self, candle: Candle) -> bool:
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            raise ValueError("candle prices must be positive")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError("invalid candle OHLC")
        if candle.volume < 0:
            raise ValueError("candle volume cannot be negative")
        key = (candle.symbol.upper(), candle.timeframe)
        items = self._candles.setdefault(key, [])
        if items and candle.timestamp <= items[-1].timestamp:
            return False
        items.append(candle)
        self._candles[key] = items[-5000:]
        return True

    def ingest_tick(self, tick: MarketTick) -> bool:
        if tick.price <= 0 or tick.volume < 0:
            raise ValueError("invalid market tick")
        symbol = tick.symbol.upper()
        if symbol in self._last_tick and tick.timestamp <= self._last_tick[symbol]:
            return False
        self._last_tick[symbol] = tick.timestamp
        return True

    def ingest_broker_candles(
        self,
        symbol: str,
        timeframe: str,
        rows: list[dict[str, Any]],
    ) -> int:
        """Normalize broker rows as an atomic batch before mutating the canonical store."""
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
                normalized.append(
                    Candle(
                        timestamp=_utc(timestamp),
                        symbol=symbol,
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
        accepted = sum(1 for candle in normalized if self.put(candle))
        return accepted

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if limit <= 0:
            return []
        return self._candles.get((symbol.upper(), timeframe), [])[-limit:]


market_data = InMemoryMarketData()
