from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from threading import RLock

from .models import Candle, Instrument, Timeframe


class HistoricalCandleRepository:
    """Provider-independent candle repository contract with in-memory storage."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._candles: dict[tuple[str, str, Timeframe, datetime], Candle] = {}

    @staticmethod
    def _key(candle: Candle) -> tuple[str, str, Timeframe, datetime]:
        return (candle.instrument.exchange, candle.instrument.symbol, candle.timeframe, candle.timestamp.astimezone(timezone.utc))

    def upsert(self, candles: Sequence[Candle]) -> int:
        prepared = [(self._key(candle), candle) for candle in candles]
        with self._lock:
            for key, candle in prepared:
                self._candles[key] = candle
        return len(prepared)

    def get(self, instrument: Instrument, timeframe: Timeframe, start: datetime, end: datetime) -> list[Candle]:
        if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("start and end must be timezone-aware")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        if end < start:
            raise ValueError("end must be >= start")
        with self._lock:
            result = [c for (exchange, symbol, tf, ts), c in self._candles.items()
                      if exchange == instrument.exchange and symbol == instrument.symbol and tf == timeframe and start <= ts <= end]
        return sorted(result, key=lambda candle: candle.timestamp)

    def count(self) -> int:
        with self._lock:
            return len(self._candles)


class SqlAlchemyHistoricalCandleRepository:
    """Durable implementation of the existing historical candle contract."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _symbol(instrument: Instrument) -> str:
        return f"{instrument.exchange}:{instrument.symbol}"

    def upsert(self, candles: Sequence[Candle]) -> int:
        from sqlalchemy import select
        from app.models.market_candle import MarketCandle

        prepared = list(candles)
        with self._session_factory() as session:
            for candle in prepared:
                timestamp = candle.timestamp.astimezone(timezone.utc)
                row = session.scalar(select(MarketCandle).where(
                    MarketCandle.symbol == self._symbol(candle.instrument),
                    MarketCandle.timeframe == candle.timeframe.value,
                    MarketCandle.timestamp == timestamp,
                ))
                if row is None:
                    session.add(MarketCandle(
                        symbol=self._symbol(candle.instrument), timeframe=candle.timeframe.value,
                        timestamp=timestamp, open=candle.open, high=candle.high,
                        low=candle.low, close=candle.close, volume=candle.volume,
                    ))
                else:
                    row.open, row.high, row.low, row.close, row.volume = candle.open, candle.high, candle.low, candle.close, candle.volume
            session.commit()
        return len(prepared)

    def get(self, instrument: Instrument, timeframe: Timeframe, start: datetime, end: datetime) -> list[Candle]:
        from sqlalchemy import select
        from app.models.market_candle import MarketCandle

        if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("start and end must be timezone-aware")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        if end < start:
            raise ValueError("end must be >= start")
        with self._session_factory() as session:
            rows = session.scalars(select(MarketCandle).where(
                MarketCandle.symbol == self._symbol(instrument),
                MarketCandle.timeframe == timeframe.value,
                MarketCandle.timestamp >= start,
                MarketCandle.timestamp <= end,
            ).order_by(MarketCandle.timestamp)).all()
        return [Candle(instrument, timeframe, r.timestamp, r.open, r.high, r.low, r.close, r.volume) for r in rows]

    def count(self) -> int:
        from sqlalchemy import func, select
        from app.models.market_candle import MarketCandle
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(MarketCandle)) or 0)
