from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from app.ict_engine import ICTEngine
from app.market_context import Candle, MarketContext
from app.market_structure import MarketStructureEngine
from app.smc_engine import SMCEngine
from app.technical_analysis import TechnicalAnalysisEngine


class UnifiedAnalysisPipeline:
    """Build one canonical, validated MarketContext from the same candle series."""

    def __init__(self, technical=None, structure=None, smc=None, ict=None):
        self.technical = technical or TechnicalAnalysisEngine()
        self.structure = structure or MarketStructureEngine()
        self.smc = smc or SMCEngine()
        self.ict = ict or ICTEngine()

    @staticmethod
    def _regime(indicators, structure) -> str:
        adx = indicators.values.get("adx_14")
        rsi = indicators.values.get("rsi_14")
        if adx is not None and adx >= 25:
            if structure.trend in {"BULLISH", "BEARISH"}:
                return "TRENDING"
            return "VOLATILE"
        if rsi is not None and 40 <= rsi <= 60:
            return "RANGING"
        return "UNKNOWN"

    @staticmethod
    def _data_quality(candles: Sequence[Candle]) -> str:
        if len(candles) < 20:
            return "DEGRADED"
        for i, candle in enumerate(candles):
            if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
                return "INVALID"
            if i and candle.timestamp <= candles[i - 1].timestamp:
                return "INVALID"
        return "GOOD"

    def build(self, symbol: str, timeframe: str, candles: Sequence[Candle]) -> MarketContext:
        if not candles:
            raise ValueError("candles are required")
        indicators = self.technical.analyze(candles)
        structure = self.structure.analyze(candles)
        smc = self.smc.analyze(candles)
        ict = self.ict.analyze(candles)
        context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            as_of=candles[-1].timestamp,
            candles=tuple(candles),
            indicators=indicators,
            structure=structure,
            smc=smc,
            ict=ict,
            regime=self._regime(indicators, structure),
            data_quality=self._data_quality(candles),
            features={
                "last_close": candles[-1].close,
                "candle_count": len(candles),
                "indicator_count": len(indicators.values),
                "order_block_count": len(smc.order_blocks),
                "fvg_count": len(smc.fair_value_gaps),
                "equal_high_count": len(smc.equal_highs),
                "equal_low_count": len(smc.equal_lows),
            },
        )
        context.validate()
        return context
