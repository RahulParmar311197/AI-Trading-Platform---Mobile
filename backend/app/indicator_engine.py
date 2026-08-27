from __future__ import annotations

from typing import Sequence

from app.market_context import Candle, IndicatorSnapshot
from app.technical_indicators import calculate_indicators as _calculate_indicators


def calculate_indicators(candles: Sequence[Candle]) -> IndicatorSnapshot:
    """Canonical adapter around the repository's established indicator engine."""
    return IndicatorSnapshot(values=dict(_calculate_indicators(candles)))
