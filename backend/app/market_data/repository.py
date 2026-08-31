from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from threading import RLock

from .models import Candle, Instrument, Timeframe


class HistoricalCandleRepository:
    """Provider-independent historical candle repository.

    The initial implementation is an in-process deterministic store so the
    market-data contract can be exercised without coupling it to a database.
    A durable adapter can implement the same semantics later.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._candles: dict[tuple[str, str, Timeframe, datetime], Candle] = {}

    @staticmethod
    def _key(candle: Candle) -> tuple[str, str, Timeframe, datetime]:
        return (
            candle.instrument.exchange,
            candle.instrument.symbol,
            candle.timeframe,
            candle.timestamp.astimezone(timezone.utc),
        )

    def upsert(self, candles: Sequence[Candle]) -> int:
        """Insert or replace candles by their canonical identity.

        Returns the number of unique identities written. The operation is
        atomic with respect to readers of this repository.
        """
        prepared = [(self._key(candle), candle) for candle in candles]
        with self._lock:
            for key, candle in prepared:
                self._candles[key] = candle
        return len(prepared)

    def get(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("start must be timezone-aware")
        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("end must be timezone-aware")
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        if end < start:
            raise ValueError("end must be >= start")

        exchange = instrument.exchange
        symbol = instrument.symbol
        with self._lock:
            result = [
                candle
                for (item_exchange, item_symbol, item_timeframe, timestamp), candle in self._candles.items()
                if item_exchange == exchange
                and item_symbol == symbol
                and item_timeframe == timeframe
                and start <= timestamp <= end
            ]
        return sorted(result, key=lambda candle: candle.timestamp)

    def count(self) -> int:
        with self._lock:
            return len(self._candles)
