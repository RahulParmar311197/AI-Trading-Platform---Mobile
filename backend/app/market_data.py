from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

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
            raise ValueError('candle prices must be positive')
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError('invalid candle OHLC')
        if candle.volume < 0:
            raise ValueError('candle volume cannot be negative')
        key = (candle.symbol.upper(), candle.timeframe)
        items = self._candles.setdefault(key, [])
        if items and candle.timestamp <= items[-1].timestamp:
            return False
        items.append(candle)
        self._candles[key] = items[-5000:]
        return True

    def ingest_tick(self, tick: MarketTick) -> bool:
        if tick.price <= 0 or tick.volume < 0:
            raise ValueError('invalid market tick')
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
