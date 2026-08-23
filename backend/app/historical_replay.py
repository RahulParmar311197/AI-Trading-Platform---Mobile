from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Iterator

from app.market_data import Candle
from app.market_data_store import MarketDataStore


@dataclass(frozen=True)
class ReplayConfig:
    symbol: str
    timeframe: str
    start: datetime | None = None
    end: datetime | None = None
    batch_size: int = 500


class HistoricalReplay:
    """Deterministic, read-only candle replay for backtests and research."""

    def __init__(self, store: MarketDataStore):
        self.store = store

    def stream(self, config: ReplayConfig) -> Iterator[Candle]:
        if config.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        cursor = config.start
        while True:
            rows = self.store.candles(
                config.symbol,
                config.timeframe,
                start=cursor,
                end=config.end,
                limit=config.batch_size,
            )
            if not rows:
                return
            for row in rows:
                if config.end is not None and row.timestamp > config.end:
                    return
                yield row
            last = rows[-1].timestamp
            if cursor is not None and last <= cursor:
                raise RuntimeError("replay cursor did not advance")
            cursor = last
            if len(rows) < config.batch_size:
                return

    def collect(self, config: ReplayConfig) -> list[Candle]:
        return list(self.stream(config))
