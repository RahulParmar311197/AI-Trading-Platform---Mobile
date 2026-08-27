from __future__ import annotations

from typing import Sequence

from app.ai_decision_engine import AIDecisionEngine
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

    def signal(self, index: int, candles: Sequence[Candle]) -> tuple[str, int] | None:
        """Return a backtest signal from information available at this bar only.

        Quantity remains supplied by the backtest/risk layer; the AI layer only decides direction.
        """
        if index < 0 or index >= len(candles):
            raise IndexError("backtest index out of range")
        visible = tuple(candles[: index + 1])
        if len(visible) < 50:
            return None
        as_of = visible[-1].timestamp
        context = self.context_builder.build(
            self.symbol,
            self.timeframe,
            visible,
            as_of=as_of,
        )
        decision = self.decision_engine.decide(context)
        if decision.decision == "HOLD":
            return None
        # Keep sizing outside the AI strategy. One unit is a neutral signal contract;
        # the production risk layer can replace this quantity before execution.
        return decision.decision, 1
