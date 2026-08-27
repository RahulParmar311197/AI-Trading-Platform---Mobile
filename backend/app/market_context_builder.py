from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from app.ai_features import build_features
from app.ai_decision_engine import AIDecisionEngine
from app.ict_engine import ICTEngine
from app.market_context import MarketContext
from app.market_structure import MarketStructureEngine
from app.smc_engine import SMCEngine
from app.technical_indicators import calculate_indicators


class MarketContextBuilder:
    """Build the canonical AI MarketContext from one candle window.

    This class composes existing analysis engines; it never places orders.
    """

    def __init__(self) -> None:
        self.structure = MarketStructureEngine()
        self.smc = SMCEngine()
        self.ict = ICTEngine()

    def build(
        self,
        symbol: str,
        candles: Sequence[Mapping[str, Any]],
        timestamp: datetime | None = None,
    ) -> MarketContext:
        if not candles:
            raise ValueError("at least one candle is required")
        indicators = calculate_indicators(candles)
        features = build_features(candles)
        structure = self.structure.analyze(candles)
        smc = self.smc.analyze(candles)
        ict = self.ict.analyze(candles, timestamp=timestamp)
        merged = {**features, **indicators}
        return MarketContext(
            symbol=symbol,
            timeframe=str(candles[-1].get("timeframe", "")),
            indicators=merged,
            structure=structure,
            smc=smc,
            ict=ict,
            regime="TRENDING" if structure.trend in {"BULLISH", "BEARISH"} else "RANGING" if structure.trend == "RANGE" else "UNKNOWN",
        )
