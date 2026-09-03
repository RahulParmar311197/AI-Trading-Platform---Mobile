"""Canonical market-data contracts and deterministic runtime helpers."""

from .models import Candle, Instrument, Tick, Timeframe
from .provider import HistoricalMarketDataProvider, RealtimeMarketDataProvider
from .runtime import (
    InMemoryMarketData,
    MarketDataFreshness,
    TickCandleAggregator,
    timeframe_seconds,
    validate_candle_sequence,
    validate_freshness,
)

# Backwards-compatible name; new code should use the canonical ``Tick`` model.
MarketTick = Tick

__all__ = [
    "Candle",
    "Instrument",
    "Tick",
    "MarketTick",
    "Timeframe",
    "HistoricalMarketDataProvider",
    "RealtimeMarketDataProvider",
    "InMemoryMarketData",
    "MarketDataFreshness",
    "TickCandleAggregator",
    "timeframe_seconds",
    "validate_candle_sequence",
    "validate_freshness",
]
