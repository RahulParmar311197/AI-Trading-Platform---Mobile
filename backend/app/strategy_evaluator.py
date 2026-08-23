"""Deterministic evaluator for the canonical strategy DSL."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.market_data import Candle
from app.strategy_dsl import ConditionType, StrategyDefinition, validate_strategy
from app.strategy_dsl_adapter import StrategyEvaluationPlan, compile_strategy
from app.unified_signal import UnifiedSignalEngine


@dataclass(frozen=True)
class EvaluationResult:
    matched: bool
    score: float
    confidence: float
    direction: str
    reasons: tuple[str, ...]
    strategy: dict[str, Any]


class StrategyEvaluator:
    """Evaluate only supported DSL conditions using existing deterministic engines.

    Unknown conditions fail closed. This class never places orders and never
    overrides the risk/execution layer.
    """

    def __init__(self, signal_engine: UnifiedSignalEngine | None = None):
        self.signal_engine = signal_engine or UnifiedSignalEngine()

    def evaluate(self, strategy: StrategyDefinition, candles: list[Candle]) -> EvaluationResult:
        validate_strategy(strategy)
        if not candles:
            return EvaluationResult(False, 0.0, 0.0, "NEUTRAL", ("NO_MARKET_DATA",), compile_strategy(strategy).strategy)

        plan = compile_strategy(strategy)
        signal = self.signal_engine.analyze(candles)
        direction = signal["direction"]
        reasons = list(signal.get("reasons", []))
        supported = {item.value for item in ConditionType}
        matched_conditions = 0

        for condition in strategy.conditions:
            if condition.type.value not in supported:
                reasons.append(f"UNSUPPORTED_CONDITION:{condition.type.value}")
                continue
            if self._condition_matches(condition, signal):
                matched_conditions += 1
            else:
                reasons.append(f"CONDITION_NOT_MET:{condition.type.value}")

        ratio = matched_conditions / len(strategy.conditions)
        direction_ok = strategy.direction.lower() == "both" or (
            strategy.direction.lower() == "bullish" and direction == "BULLISH"
        ) or (
            strategy.direction.lower() == "bearish" and direction == "BEARISH"
        )
        score = ratio if direction_ok else 0.0
        matched = direction_ok and matched_conditions == len(strategy.conditions) and bool(signal.get("tradeable"))
        if not direction_ok:
            reasons.append("DIRECTION_NOT_CONFIRMED")

        return EvaluationResult(
            matched=matched,
            score=score,
            confidence=min(float(signal.get("confidence", 0.0)), score),
            direction=direction,
            reasons=tuple(reasons),
            strategy=plan.strategy,
        )

    @staticmethod
    def _condition_matches(condition, signal: dict[str, Any]) -> bool:
        if condition.type == ConditionType.TREND:
            wanted = str(condition.value or "").upper()
            return wanted in {"", signal.get("direction", "")}
        if condition.type in {ConditionType.BOS, ConditionType.MSS, ConditionType.CHOCH, ConditionType.LIQUIDITY_SWEEP, ConditionType.FVG, ConditionType.ORDER_BLOCK, ConditionType.PREMIUM_DISCOUNT}:
            smc = signal.get("smc") or {}
            wanted = str(condition.value or "").lower()
            text = str(smc).lower()
            return not wanted or wanted in text
        if condition.type == ConditionType.INDICATOR:
            technical = signal.get("technical")
            wanted = str(condition.parameters.get("trend", "")).upper()
            return not wanted or getattr(technical, "trend", "") == wanted
        # Conditions needing dedicated volume/options/session providers remain
        # explicit extension points and fail closed until those providers are wired.
        return False
