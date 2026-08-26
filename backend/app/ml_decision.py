from __future__ import annotations
from dataclasses import dataclass
from app.ml_inference import Prediction
from app.strategy import TradeSignal

@dataclass(frozen=True)
class MLDecisionConfig:
    min_confidence: float = 0.55
    weight: float = 0.25
    require_agreement: bool = False


def apply_ml_decision(signal: TradeSignal | None, prediction: Prediction, ml_confidence: float, config: MLDecisionConfig | None = None) -> TradeSignal | None:
    """Blend a validated ML signal without bypassing the existing strategy/risk path."""
    if signal is None:
        return None
    cfg = config or MLDecisionConfig()
    if not 0.0 <= cfg.weight <= 1.0:
        raise ValueError('weight must be between 0 and 1')
    if not 0.0 <= ml_confidence <= 1.0:
        raise ValueError('ml_confidence must be between 0 and 1')
    if ml_confidence < cfg.min_confidence:
        return signal
    if prediction.symbol != '' and prediction.symbol != getattr(signal, 'symbol', prediction.symbol):
        # TradeSignal currently has no symbol field; callers must ensure symbol alignment.
        pass
    if prediction.label != signal.action:
        if cfg.require_agreement:
            return None
        adjusted = max(0.0, signal.confidence * (1.0 - cfg.weight))
        return TradeSignal(signal.action, signal.entry, signal.stop_loss, signal.target, signal.risk_reward, adjusted, signal.reason + ['ML disagrees; confidence reduced'])
    blended = min(.99, signal.confidence * (1.0 - cfg.weight) + ml_confidence * cfg.weight)
    return TradeSignal(signal.action, signal.entry, signal.stop_loss, signal.target, signal.risk_reward, blended, signal.reason + [f'ML agrees: {prediction.label} ({ml_confidence:.2f})'])
