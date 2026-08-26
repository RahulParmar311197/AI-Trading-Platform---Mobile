from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import AIDecisionEngine
from app.analysis_pipeline import UnifiedAnalysisPipeline
from app.market_context import MarketContext
from app.market_data import Candle


@dataclass(frozen=True)
class DecisionCycleResult:
    """Result of one deterministic AI decision cycle."""

    context: MarketContext
    decision: object


class DecisionCycleService:
    """Canonical bridge from market candles to the AI trading decision.

    This service deliberately stops at TradingDecision. It does not perform
    risk authorization, broker calls, order submission, or scheduling.
    Those responsibilities remain in the existing downstream services.
    """

    def __init__(
        self,
        analysis_pipeline: UnifiedAnalysisPipeline | None = None,
        decision_engine: AIDecisionEngine | None = None,
    ) -> None:
        self.analysis_pipeline = analysis_pipeline or UnifiedAnalysisPipeline()
        self.decision_engine = decision_engine or AIDecisionEngine()

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> DecisionCycleResult:
        context = self.analysis_pipeline.build(symbol, timeframe, candles)
        decision = self.decision_engine.decide(context)
        return DecisionCycleResult(context=context, decision=decision)
