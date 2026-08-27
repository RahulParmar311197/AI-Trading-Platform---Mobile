from __future__ import annotations

from typing import Sequence

from app.ai_decision_engine import AIDecisionEngine, TradingDecision
from app.market_context import Candle
from app.market_context_builder import MarketContextBuilder


class CanonicalAIBacktestStrategy:
    """Adapts the live AI decision path to the existing backtest signal contract."""

    def __init__(
        self,
        *,
        decision_engine: AIDecisionEngine | None = None,
        context_builder: MarketContextBuilder | None = None,
        symbol: str,
        timeframe: str,
    ) -> None:
        self.decision_engine = decision_engine or AIDecisionEngine()
        self.context_builder = context_builder or MarketContextBuilder()
        self.symbol = symbol
        self.timeframe = timeframe

    def decision(self, index: int, candles: Sequence[Candle]) -> TradingDecision:
        """Evaluate exactly once from information available at this bar only."""
        if index < 0 or index >= len(candles):
            raise IndexError("backtest index out of range")
        visible = tuple(candles[: index + 1])
        if len(visible) < 50:
            raise ValueError("insufficient candles for canonical AI decision")
        as_of = visible[-1].timestamp
        context = self.context_builder.build(
            self.symbol,
            self.timeframe,
            visible,
            as_of=as_of,
        )
        return self.decision_engine.decide(context)

    def signal(self, index: int, candles: Sequence[Candle]) -> tuple[str, int] | None:
        """Return a backtest signal from information available at this bar only.

        Quantity remains supplied by the backtest/risk layer; the AI layer only decides direction.
        """
        if index < 0 or index >= len(candles):
            raise IndexError("backtest index out of range")
        visible = tuple(candles[: index + 1])
        if len(visible) < 50:
            return None
        decision = self.decision(index, candles)
        if decision.decision == "HOLD":
            return None
        return decision.decision, 1
