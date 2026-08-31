from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import floor

from .models import Candle, Tick, Timeframe

_TIMEFRAME_SECONDS = {
    Timeframe.ONE_MINUTE: 60,
    Timeframe.THREE_MINUTES: 180,
    Timeframe.FIVE_MINUTES: 300,
    Timeframe.FIFTEEN_MINUTES: 900,
    Timeframe.THIRTY_MINUTES: 1800,
    Timeframe.ONE_HOUR: 3600,
    Timeframe.FOUR_HOURS: 14400,
    Timeframe.ONE_DAY: 86400,
    Timeframe.ONE_WEEK: 604800,
}


class CandleAggregator:
    """Deterministically aggregates ticks into UTC timeframe candles.

    Ticks older than the current bucket are rejected once a bucket has closed.
    This prevents a late tick from silently rewriting already-emitted history.
    """

    def __init__(self, timeframe: Timeframe):
        self.timeframe = timeframe
        self._seconds = _TIMEFRAME_SECONDS[timeframe]
        self._current: Candle | None = None

    def _bucket_start(self, timestamp: datetime) -> datetime:
        timestamp = timestamp.astimezone(timezone.utc)
        epoch = timestamp.timestamp()
        bucket = floor(epoch / self._seconds) * self._seconds
        return datetime.fromtimestamp(bucket, tz=timezone.utc)

    @property
    def current(self) -> Candle | None:
        return self._current

    def update(self, tick: Tick) -> Candle | None:
        bucket = self._bucket_start(tick.timestamp)
        if self._current is None:
            self._current = Candle(
                instrument=tick.instrument,
                timeframe=self.timeframe,
                timestamp=bucket,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume,
            )
            return None

        if tick.instrument != self._current.instrument:
            raise ValueError("tick instrument does not match active candle")

        if bucket < self._current.timestamp:
            raise ValueError("out-of-order tick belongs to a closed candle")

        if bucket == self._current.timestamp:
            self._current = self._current.model_copy(
                update={
                    "high": max(self._current.high, tick.price),
                    "low": min(self._current.low, tick.price),
                    "close": tick.price,
                    "volume": self._current.volume + tick.volume,
                }
            )
            return None

        completed = self._current
        if bucket > completed.timestamp + timedelta(seconds=self._seconds):
            # Empty intervals are deliberately not synthesized. Consumers can
            # distinguish a genuine gap from a zero-volume candle.
            pass

        self._current = Candle(
            instrument=tick.instrument,
            timeframe=self.timeframe,
            timestamp=bucket,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.volume,
        )
        return completed

    def flush(self) -> Candle | None:
        completed = self._current
        self._current = None
        return completed
