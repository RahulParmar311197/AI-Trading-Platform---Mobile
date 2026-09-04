from datetime import datetime, timedelta, timezone

import pytest

from app.ai_decision import AIDecisionEngine
from app.market_data import Candle
from app.ml_decision import MLDecisionConfig
from app.ml_inference import Prediction


def bars(n=60):
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            "NIFTY",
            "15m",
            t + timedelta(minutes=15 * i),
            100 + i,
            102 + i,
            99 + i,
            101 + i,
            1000 + i * 5,
        )
        for i in range(n)
    ]


def test_empty_market_waits():
    d = AIDecisionEngine().decide([])
    assert d.action == "WAIT"
    assert not d.tradeable


def test_invalid_confidence_rejected():
    with pytest.raises(ValueError):
        AIDecisionEngine(1.1)
    with pytest.raises(ValueError):
        AIDecisionEngine(float("nan"))
    with pytest.raises(ValueError):
        AIDecisionEngine(True)


def test_invalid_ml_confidence_rejected():
    with pytest.raises(ValueError):
        AIDecisionEngine().decide(bars(), ml_confidence=float("nan"))
    with pytest.raises(ValueError):
        AIDecisionEngine().decide(bars(), ml_confidence=1.1)


def test_invalid_prediction_fails_closed():
    last = bars()[-1].timestamp
    prediction = Prediction("BANKNIFTY", last, "BUY", "model", "1")
    d = AIDecisionEngine().decide(bars(), prediction, 0.9)
    assert d.action == "WAIT"
    assert not d.tradeable
    assert d.reasons == ("INVALID_ML_PREDICTION",)


def test_future_prediction_fails_closed():
    future = bars()[-1].timestamp + timedelta(minutes=1)
    prediction = Prediction("NIFTY", future, "BUY", "model", "1")
    d = AIDecisionEngine().decide(bars(), prediction, 0.9)
    assert d.action == "WAIT"
    assert not d.tradeable


def test_ml_config_is_validated():
    with pytest.raises(ValueError):
        AIDecisionEngine(ml_config=MLDecisionConfig(weight=float("nan")))
    with pytest.raises(ValueError):
        AIDecisionEngine(ml_config=MLDecisionConfig(min_confidence=1.1))


def test_decision_has_explanation():
    d = AIDecisionEngine(0.0).decide(bars())
    assert d.action in {"BUY", "SELL", "WAIT"}
    assert isinstance(d.reasons, tuple)
    assert all(isinstance(reason, str) for reason in d.reasons)
    assert 0.0 <= d.confidence <= 1.0
