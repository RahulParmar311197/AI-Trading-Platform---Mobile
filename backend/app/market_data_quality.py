from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Sequence

from app.market_context import Candle


@dataclass(frozen=True)
class DataQuality:
    status: str
    reasons: tuple[str, ...]


def assess_data_quality(
    candles: Sequence[Candle],
    *,
    as_of: datetime | None = None,
    min_history: int = 50,
    max_age: timedelta = timedelta(minutes=10),
) -> DataQuality:
    if not candles:
        return DataQuality("INVALID", ("no candles",))
    reasons: list[str] = []
    previous = None
    for candle in candles:
        if previous is not None and candle.timestamp <= previous:
            reasons.append("timestamps are not strictly increasing")
        previous = candle.timestamp
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if not all(math.isfinite(float(v)) for v in values):
            reasons.append("non-finite OHLCV value")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close) or candle.low > candle.high or candle.volume < 0:
            reasons.append("invalid OHLCV relationship")
    if len(candles) < min_history:
        reasons.append(f"insufficient history: {len(candles)} < {min_history}")
    reference = as_of or datetime.now(timezone.utc)
    latest = candles[-1].timestamp
    age = reference - latest
    if age > max_age:
        reasons.append(f"latest candle stale: {age}")
    if age.total_seconds() < -60:
        reasons.append("latest candle is in the future")
    unique_reasons = tuple(dict.fromkeys(reasons))
    if any("stale" in r or "future" in r for r in unique_reasons):
        return DataQuality("STALE", unique_reasons)
    if any("timestamps" in r or "non-finite" in r or "invalid OHLCV" in r or "no candles" in r for r in unique_reasons):
        return DataQuality("INVALID", unique_reasons)
    if unique_reasons:
        return DataQuality("DEGRADED", unique_reasons)
    return DataQuality("GOOD", ())
