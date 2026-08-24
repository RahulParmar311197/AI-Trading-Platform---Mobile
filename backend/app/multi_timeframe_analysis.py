from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.analysis_pipeline import UnifiedAnalysisPipeline
from app.market_context import Candle, MarketContext


@dataclass(frozen=True)
class MultiTimeframeContext:
    """Higher-timeframe context plus execution-timeframe context."""
    higher: MarketContext
    execution: MarketContext

    @property
    def aligned(self) -> bool:
        if self.higher.structure.trend == "UNKNOWN" or self.execution.structure.trend == "UNKNOWN":
            return False
        return self.higher.structure.trend == self.execution.structure.trend


class MultiTimeframeAnalysis:
    """Builds deterministic contexts for HTF bias and LTF execution analysis."""

    def __init__(self, pipeline: UnifiedAnalysisPipeline | None = None):
        self.pipeline = pipeline or UnifiedAnalysisPipeline()

    def build(
        self,
        symbol: str,
        higher_timeframe: str,
        higher_candles: Sequence[Candle],
        execution_timeframe: str,
        execution_candles: Sequence[Candle],
    ) -> MultiTimeframeContext:
        if not higher_candles or not execution_candles:
            raise ValueError("both higher and execution timeframe candles are required")
        higher = self.pipeline.build(symbol, higher_timeframe, higher_candles)
        execution = self.pipeline.build(symbol, execution_timeframe, execution_candles)
        return MultiTimeframeContext(higher=higher, execution=execution)
