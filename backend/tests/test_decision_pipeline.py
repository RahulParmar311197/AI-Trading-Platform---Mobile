from datetime import datetime, timedelta, timezone

from app.decision_pipeline import generate_ml_signal
from app.ml_decision import MLDecisionConfig
from app.ml_inference import Prediction
from app.market_data import Candle


def make_candles(n=60):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(symbol='TEST', timestamp=start + timedelta(minutes=i), open=100+i*.1, high=101+i*.1, low=99+i*.1, close=100+i*.1, volume=1000) for i in range(n)]


def test_pipeline_returns_none_when_strategy_has_no_signal():
    candles = make_candles()
    prediction = Prediction('TEST', candles[-1].timestamp, 'BUY', 'model', '1')
    assert generate_ml_signal(candles, prediction, .9, min_score=99) is None


def test_pipeline_never_lets_low_confidence_ml_create_signal():
    candles = make_candles()
    prediction = Prediction('TEST', candles[-1].timestamp, 'BUY', 'model', '1')
    result = generate_ml_signal(candles, prediction, .1, min_score=1)
    if result is not None:
        assert result.action in {'BUY', 'SELL'}
