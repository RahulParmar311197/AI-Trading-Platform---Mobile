from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data import Candle
from app.models import MarketCandle


class MarketDataStore:
    """Durable OHLCV storage with idempotent candle upserts and ordered reads."""

    def __init__(self, db: Session):
        self.db = db

    def upsert(self, candle: Candle) -> MarketCandle:
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            raise ValueError("candle prices must be positive")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError("invalid candle OHLC")
        if candle.volume < 0:
            raise ValueError("candle volume cannot be negative")
        symbol = candle.symbol.strip().upper()
        row = self.db.scalar(
            select(MarketCandle).where(
                MarketCandle.symbol == symbol,
                MarketCandle.timeframe == candle.timeframe,
                MarketCandle.timestamp == candle.timestamp,
            )
        )
        if row is None:
            row = MarketCandle(symbol=symbol, timeframe=candle.timeframe, timestamp=candle.timestamp)
            self.db.add(row)
        row.open = candle.open
        row.high = candle.high
        row.low = candle.low
        row.close = candle.close
        row.volume = candle.volume
        self.db.flush()
        return row

    def candles(self, symbol: str, timeframe: str, start: datetime | None = None, end: datetime | None = None, limit: int = 2000) -> list[Candle]:
        if limit <= 0:
            return []
        statement = select(MarketCandle).where(
            MarketCandle.symbol == symbol.strip().upper(),
            MarketCandle.timeframe == timeframe,
        )
        if start is not None:
            statement = statement.where(MarketCandle.timestamp >= start)
        if end is not None:
            statement = statement.where(MarketCandle.timestamp <= end)
        rows = list(self.db.scalars(statement.order_by(MarketCandle.timestamp.desc()).limit(limit)).all())
        rows.reverse()
        return [Candle(timestamp=r.timestamp, symbol=r.symbol, timeframe=r.timeframe, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume) for r in rows]
