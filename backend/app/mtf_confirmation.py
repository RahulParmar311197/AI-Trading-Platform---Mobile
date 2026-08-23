from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from app.mtf_aggregator import Candle, MultiTimeframeAggregator, TIMEFRAME_SECONDS

@dataclass(frozen=True)
class MTFContext:
    bias: str
    timeframe: str
    candle_timestamp: datetime | None
    close: float | None


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def completed_htf_context(ltf_timestamp: datetime, candles: list[Candle], htf: str) -> MTFContext:
    if htf not in TIMEFRAME_SECONDS:
        raise ValueError('unsupported timeframe')
    ts = _utc(ltf_timestamp)
    aggregated = MultiTimeframeAggregator().aggregate(candles, htf)
    completed = [c for c in aggregated if _utc(c.timestamp) + __import__('datetime').timedelta(seconds=TIMEFRAME_SECONDS[htf]) <= ts]
    if not completed:
        return MTFContext('NEUTRAL', htf, None, None)
    c = completed[-1]
    first = candles[0] if candles else None
    if first is None:
        return MTFContext('NEUTRAL', htf, c.timestamp, c.close)
    bias = 'BULLISH' if c.close > c.open else 'BEARISH' if c.close < c.open else 'NEUTRAL'
    return MTFContext(bias, htf, c.timestamp, c.close)


def confirms(side: str, context: MTFContext, require_alignment: bool = True) -> bool:
    if not require_alignment:
        return True
    if side == 'BUY':
        return context.bias == 'BULLISH'
    if side == 'SELL':
        return context.bias == 'BEARISH'
    return False
