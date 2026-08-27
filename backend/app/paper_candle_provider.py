from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.candle_provider import CandleProvider, normalize_candles
from app.market_context import Candle


class PaperCandleProvider(CandleProvider):
    """Deterministic in-memory provider for paper/backtest integration tests."""

    def __init__(self, candles: Sequence[Candle]) -> None:
        self._candles = normalize_candles(candles)

    async def historical(
        self,
        symbol: str,
        *,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> tuple[Candle, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        values = self._candles
        if start is not None:
            values = tuple(c for c in values if c.timestamp >= start)
        if end is not None:
            values = tuple(c for c in values if c.timestamp <= end)
        return tuple(values[-limit:])

    async def latest(
        self,
        symbol: str,
        *,
        interval: str,
        limit: int = 100,
    ) -> tuple[Candle, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return tuple(self._candles[-limit:])
