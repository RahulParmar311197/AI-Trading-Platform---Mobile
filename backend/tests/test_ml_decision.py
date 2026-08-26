from datetime import datetime, timezone
import pytest
from app.ml_decision import MLDecisionConfig, apply_ml_decision
from app.ml_inference import Prediction
from app.strategy import TradeSignal


def signal(action='BUY'):
    return TradeSignal(action, 100, 98, 106, 3.0, .70, ['strategy'])


def prediction(label='BUY'):
    return Prediction('TEST', datetime.now(timezone.utc), label, 'model', '1')


def test_agreement_blends_confidence():
    result = apply_ml_decision(signal(), prediction(), .90)
    assert result is not None
    assert result.confidence > .70


def test_disagreement_reduces_confidence():
    result = apply_ml_decision(signal(), prediction('SELL'), .90)
    assert result is not None
    assert result.confidence < .70


def test_low_ml_confidence_leaves_signal_unchanged():
    original = signal()
    result = apply_ml_decision(original, prediction(), .40)
    assert result == original


def test_required_agreement_rejects_disagreement():
    result = apply_ml_decision(signal(), prediction('SELL'), .90, MLDecisionConfig(require_agreement=True))
    assert result is None


def test_weight_validation():
    with pytest.raises(ValueError):
        apply_ml_decision(signal(), prediction(), .90, MLDecisionConfig(weight=1.1))
