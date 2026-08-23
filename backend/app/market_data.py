from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
                # Legacy: (symbol, timeframe, timestamp, open, high, low, close, volume)
                positional_fields = ("symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume")
            elif isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], datetime):
                if len(args) >= 3 and not isinstance(args[2], str):
                    # Legacy: (symbol, timestamp, open, high, low, close, volume)
                    positional_fields = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
                else:
                    # Legacy: (symbol, timestamp, timeframe, open, high, low, close, volume)
                    positional_fields = ("symbol", "timestamp", "timeframe", "open", "high", "low", "close", "volume")
            else:
                # Production: (timestamp, symbol, timeframe, open, high, low, close, volume)
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
        object.__setattr__(self, "timestamp", values["timestamp"])
        object.__setattr__(self, "symbol", values["symbol"])
        object.__setattr__(self, "timeframe", values["timeframe"])
        object.__setattr__(self, "open", values["open"])
        object.__setattr__(self, "high", values["high"])
        object.__setattr__(self, "low", values["low"])
        object.__setattr__(self, "close", values["close"])
        object.__setattr__(self, "volume", values["volume"])


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    timestamp: datetime
    price: float
    volume: float = 0.0


class MarketDataProvider(Protocol):
    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]: ...


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

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if limit <= 0:
            return []
        return self._candles.get((symbol.upper(), timeframe), [])[-limit:]


market_data = InMemoryMarketData()
