from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Mapping, Sequence

from app.market_context import Candle


class CandleProvider(ABC):
    """Broker-neutral source of normalized OHLCV candles."""

    @abstractmethod
    async def historical(
        self,
        symbol: str,
        *,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[Candle]:
        raise NotImplementedError

    @abstractmethod
    async def latest(
        self,
        symbol: str,
        *,
        interval: str,
        limit: int = 100,
    ) -> Sequence[Candle]:
        raise NotImplementedError


def normalize_candle(value: Candle | Mapping[str, Any] | Sequence[Any]) -> Candle:
    """Normalize common provider candle shapes into the canonical Candle model."""
    if isinstance(value, Candle):
        return value
    if isinstance(value, Mapping):
        timestamp = value.get("timestamp", value.get("time"))
        if timestamp is None:
            raise ValueError("candle timestamp is required")
        return Candle(
            timestamp=timestamp,
            open=float(value["open"]),
            high=float(value["high"]),
            low=float(value["low"]),
            close=float(value["close"]),
            volume=float(value.get("volume", 0.0)),
        )
    if len(value) != 6:
        raise ValueError("candle sequence must contain timestamp, OHLCV")
    timestamp, open_, high, low, close, volume = value
    return Candle(timestamp=timestamp, open=float(open_), high=float(high), low=float(low), close=float(close), volume=float(volume))


def normalize_candles(values: Sequence[Candle | Mapping[str, Any] | Sequence[Any]]) -> tuple[Candle, ...]:
    return tuple(normalize_candle(value) for value in values)
