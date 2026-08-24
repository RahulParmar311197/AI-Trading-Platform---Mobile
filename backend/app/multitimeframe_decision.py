from __future__ import annotations

from dataclasses import dataclass

from app.ai_decision_engine import AIDecisionEngine, DecisionConfig, TradingDecision
from app.multi_timeframe_analysis import MultiTimeframeContext


@dataclass(frozen=True)
class ConfluenceConfig:
    minimum_confidence: float = 0.60
    htf_weight: float = 0.40
    ltf_weight: float = 0.60


class MultiTimeframeDecisionEngine:
    """Combines HTF bias with LTF execution evidence without bypassing risk controls."""

    def __init__(self, decision_engine: AIDecisionEngine | None = None, config: ConfluenceConfig | None = None):
        self.engine = decision_engine or AIDecisionEngine(DecisionConfig())
        self.config = config or ConfluenceConfig()
        if self.config.htf_weight < 0 or self.config.ltf_weight < 0 or self.config.htf_weight + self.config.ltf_weight <= 0:
            raise ValueError("timeframe weights must be non-negative and have positive total")

    def decide(self, context: MultiTimeframeContext) -> TradingDecision:
        htf = self.engine.decide(context.higher)
        ltf = self.engine.decide(context.execution)
        total_weight = self.config.htf_weight + self.config.ltf_weight
        htw = self.config.htf_weight / total_weight
        ltw = self.config.ltf_weight / total_weight

        direction_scores = {"BUY": htw * htf.confidence * (1 if htf.decision == "BUY" else 0) + ltw * ltf.confidence * (1 if ltf.decision == "BUY" else 0),
                            "SELL": htw * htf.confidence * (1 if htf.decision == "SELL" else 0) + ltw * ltf.confidence * (1 if ltf.decision == "SELL" else 0)}
        aligned = context.aligned and htf.decision == ltf.decision and htf.decision in {"BUY", "SELL"}
        confidence = max(direction_scores.values())
        reasons = list(ltf.reasons)
        reasons.append(f"HTF decision={htf.decision} confidence={htf.confidence:.2f}")
        reasons.append(f"LTF decision={ltf.decision} confidence={ltf.confidence:.2f}")
        reasons.append("multi-timeframe structure aligned" if context.aligned else "multi-timeframe structure not aligned")
        reasons.append("multi-timeframe directional confirmation" if aligned else "timeframe contradiction or HOLD")

        if not aligned or confidence < self.config.minimum_confidence:
            return TradingDecision("HOLD", round(confidence, 4), round(direction_scores["BUY"], 4), round(direction_scores["SELL"], 4), None, None, None, tuple(reasons))

        # Keep the execution-timeframe levels; this layer only strengthens/blocks the proposal.
        return TradingDecision(htf.decision, round(confidence, 4), round(direction_scores["BUY"], 4), round(direction_scores["SELL"], 4), ltf.entry, ltf.stop_loss, ltf.target, tuple(reasons))
