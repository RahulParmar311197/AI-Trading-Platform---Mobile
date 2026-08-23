from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str


TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)

    return ts.astimezone(timezone.utc)


def _bucket(ts: datetime, seconds: int) -> datetime:
    ts = _utc(ts)
    epoch = int(ts.timestamp())

    return datetime.fromtimestamp(
        epoch - (epoch % seconds),
        tz=timezone.utc,
    )


class MultiTimeframeAggregator:
    def aggregate(
        self,
        candles: list[Candle],
        timeframe: str,
    ) -> list[Candle]:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError("unsupported timeframe")

        if not candles:
            return []

        seconds = TIMEFRAME_SECONDS[timeframe]
        groups: dict[datetime, list[Candle]] = {}

        for candle in sorted(
            candles,
            key=lambda item: _utc(item.timestamp),
        ):
            bucket = _bucket(candle.timestamp, seconds)
            groups.setdefault(bucket, []).append(candle)

        return [
            Candle(
                timestamp=bucket,
                open=items[0].open,
                high=max(item.high for item in items),
                low=min(item.low for item in items),
                close=items[-1].close,
                volume=sum(item.volume for item in items),
                symbol=items[0].symbol.upper(),
                timeframe=timeframe,
            )
            for bucket, items in groups.items()
        ]

    def validate_alignment(
        self,
        candles: list[Candle],
        timeframe: str,
    ) -> list[dict]:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError("unsupported timeframe")

        step = TIMEFRAME_SECONDS[timeframe]
        issues = []

        for candle in candles:
            timestamp = _utc(candle.timestamp)
            expected = _bucket(timestamp, step)

            if timestamp != expected:
                issues.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "expected_bucket": expected.isoformat(),
                    }
                )

        return issues