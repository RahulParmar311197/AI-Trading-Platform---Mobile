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


class MarketDataProvider(Protocol):
    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]: ...


class InMemoryMarketData:
    """Deterministic provider for development, tests and paper trading."""

    def __init__(self):
        self._candles: dict[tuple[str, str], list[Candle]] = {}

    def put(self, candle: Candle) -> None:
        key = (candle.symbol.upper(), candle.timeframe)
        self._candles.setdefault(key, []).append(candle)
        self._candles[key] = self._candles[key][-5000:]

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        return self._candles.get((symbol.upper(), timeframe), [])[-limit:]


market_data = InMemoryMarketData()
