from __future__ import annotations

from typing import Sequence

from app.ai_features import build_features
from app.ict_engine import ict_context
from app.market_context import Candle, MarketContext
from app.market_structure import MarketStructureEngine
from app.smc_engine import SMCEngine
from app.technical_indicators import calculate_indicators


class MarketContextBuilder:
    """Compose the existing analysis engines into one AI decision context."""

    def __init__(self) -> None:
        self.structure = MarketStructureEngine()
        self.smc = SMCEngine()

    def build(self, symbol: str, candles: Sequence[Candle]) -> MarketContext:
        if not candles:
            raise ValueError("at least one candle is required")
        candle_list = list(candles)
        features = build_features(candle_list)
        indicators = calculate_indicators(candle_list)
        structure = self.structure.analyze(candle_list)
        smc = self.smc.analyze(candle_list)
        ict = ict_context(candle_list)
        merged = {**features, **indicators, "ict_context": ict}
        regime = (
            "TRENDING" if structure.trend in {"BULLISH", "BEARISH"}
            else "RANGING" if structure.trend == "RANGING"
            else "UNKNOWN"
        )
        return MarketContext(
            symbol=symbol,
            timeframe="",
            indicators=merged,
            structure=structure,
            smc=smc,
            regime=regime,
        )
