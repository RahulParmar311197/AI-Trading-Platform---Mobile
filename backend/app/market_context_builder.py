from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.ai_features import build_features
from app.ict_engine import ict_context
from app.market_context import Candle, ICTSnapshot, IndicatorSnapshot, MarketContext
from app.market_structure import MarketStructureEngine
from app.smc_engine import SMCEngine
from app.technical_indicators import calculate_indicators


class MarketContextBuilder:
    """Compose the existing analysis engines into the canonical AI context."""

    def __init__(self) -> None:
        self.structure = MarketStructureEngine()
        self.smc = SMCEngine()

    def build(self, symbol: str, timeframe: str, candles: Sequence[Candle], as_of: datetime | None = None) -> MarketContext:
        if not symbol.strip():
            raise ValueError("symbol is required")
        if not timeframe.strip():
            raise ValueError("timeframe is required")
        if not candles:
            raise ValueError("at least one candle is required")
        candle_list = list(candles)
        features = build_features(candle_list)
        indicators = calculate_indicators(candle_list)
        structure = self.structure.analyze(candle_list)
        smc = self.smc.analyze(candle_list)
        ict_raw = ict_context(candle_list)
        ict = ICTSnapshot(
            dealing_range_high=ict_raw.get("dealing_range_high"),
            dealing_range_low=ict_raw.get("dealing_range_low"),
            optimal_trade_entry=ict_raw.get("optimal_trade_entry"),
            session=ict_raw.get("session"),
            kill_zone=ict_raw.get("kill_zone"),
            liquidity_target=ict_raw.get("liquidity_target"),
        )
        context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of or candle_list[-1].timestamp,
            candles=tuple(candle_list),
            indicators=IndicatorSnapshot(values={**features, **indicators}),
            structure=structure,
            smc=smc,
            ict=ict,
            regime=("TRENDING" if structure.trend in {"BULLISH", "BEARISH"} else "RANGING" if structure.trend == "RANGING" else "UNKNOWN"),
            features=features,
        )
        context.validate()
        return context
