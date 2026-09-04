from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from app.market_data import Candle, validate_candle_sequence
from app.ml_decision import MLDecisionConfig, apply_ml_decision
from app.ml_inference import Prediction
from app.strategy import TradeSignal
from app.unified_signal import UnifiedSignalEngine


@dataclass(frozen=True)
class AIDecision:
    action: str
    confidence: float
    score: float
    tradeable: bool
    reasons: tuple[str, ...]


class AIDecisionEngine:
    """Produce advisory decisions only; broker execution remains outside this layer."""

    def __init__(self, min_confidence: float = 0.60, ml_config: MLDecisionConfig | None = None):
        if isinstance(min_confidence, bool) or not isfinite(float(min_confidence)) or not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be finite and between 0 and 1")
        self.min_confidence = float(min_confidence)
        self.ml_config = ml_config
        if ml_config is not None:
            if isinstance(ml_config.require_agreement, bool) is False:
                raise ValueError("require_agreement must be boolean")
            if not isfinite(float(ml_config.min_confidence)) or not 0 <= ml_config.min_confidence <= 1:
                raise ValueError("ML min_confidence must be finite and between 0 and 1")
            if not isfinite(float(ml_config.weight)) or not 0 <= ml_config.weight <= 1:
                raise ValueError("ML weight must be finite and between 0 and 1")

    @staticmethod
    def _validated_prediction(prediction: Prediction, candles: list[Candle]) -> bool:
        if not isinstance(prediction, Prediction):
            return False
        symbol = candles[-1].symbol.strip().upper()
        if not prediction.symbol or prediction.symbol.strip().upper() != symbol:
            return False
        if prediction.label not in {"BUY", "SELL", "NEUTRAL"}:
            return False
        if not prediction.model_name or not prediction.model_version:
            return False
        timestamp = prediction.timestamp
        if not isinstance(timestamp, datetime):
            return False
        if timestamp.tzinfo is None:
            return False
        return timestamp <= candles[-1].timestamp

    def decide(
        self,
        candles: list[Candle],
        prediction: Prediction | None = None,
        ml_confidence: float = 0.0,
    ) -> AIDecision:
        if not candles or not validate_candle_sequence(candles):
            return AIDecision("WAIT", 0.0, 0.0, False, ("INVALID_MARKET_DATA",))
        if isinstance(ml_confidence, bool) or not isfinite(float(ml_confidence)) or not 0 <= ml_confidence <= 1:
            raise ValueError("ml_confidence must be finite and between 0 and 1")
        if prediction is not None and not self._validated_prediction(prediction, candles):
            return AIDecision("WAIT", 0.0, 0.0, False, ("INVALID_ML_PREDICTION",))

        signal = UnifiedSignalEngine().analyze(candles)
        if not isinstance(signal, dict):
            return AIDecision("WAIT", 0.0, 0.0, False, ("INVALID_SIGNAL_RESULT",))
        try:
            confidence = float(signal["confidence"])
            score = float(signal["score"])
        except (KeyError, TypeError, ValueError):
            return AIDecision("WAIT", 0.0, 0.0, False, ("INVALID_SIGNAL_RESULT",))
        direction = signal.get("direction")
        tradeable = signal.get("tradeable")
        reasons = signal.get("reasons")
        if (
            not isfinite(confidence)
            or not isfinite(score)
            or direction not in {"BULLISH", "BEARISH", "NEUTRAL"}
            or not isinstance(tradeable, bool)
            or not isinstance(reasons, list)
            or not all(isinstance(reason, str) for reason in reasons)
        ):
            return AIDecision("WAIT", 0.0, 0.0, False, ("INVALID_SIGNAL_RESULT",))

        reasons = list(reasons)
        if direction == "NEUTRAL":
            reasons.append("NO_DIRECTIONAL_EDGE")
            return AIDecision("WAIT", confidence, score, False, tuple(reasons))
        if confidence < self.min_confidence:
            reasons.append("CONFIDENCE_BELOW_THRESHOLD")
            return AIDecision("WAIT", confidence, score, False, tuple(reasons))
        if not tradeable:
            reasons.append("SIGNAL_NOT_TRADEABLE")
            return AIDecision("WAIT", confidence, score, False, tuple(reasons))

        action = "BUY" if direction == "BULLISH" else "SELL"
        if prediction is not None:
            trade_signal = TradeSignal(action, 0.0, 0.0, 0.0, 0.0, confidence, reasons)
            blended = apply_ml_decision(trade_signal, prediction, float(ml_confidence), self.ml_config)
            if blended is None:
                reasons.append("ML_DISAGREEMENT")
                return AIDecision("WAIT", confidence, score, False, tuple(reasons))
            confidence = float(blended.confidence)
            reasons = list(blended.reason)
            if not isfinite(confidence) or confidence < self.min_confidence:
                reasons.append("ML_ADJUSTED_CONFIDENCE_BELOW_THRESHOLD")
                return AIDecision("WAIT", confidence if isfinite(confidence) else 0.0, score, False, tuple(reasons))
            return AIDecision(action, confidence, score, True, tuple(reasons))

        return AIDecision(action, confidence, score, True, tuple(reasons))
