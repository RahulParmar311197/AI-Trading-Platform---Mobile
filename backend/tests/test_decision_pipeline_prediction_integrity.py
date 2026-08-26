from datetime import datetime, timezone

import app.decision_pipeline as pipeline
from app.market_data import Candle
from app.ml_inference import Prediction
from app.strategy import TradeSignal


def _candle(symbol: str = "NIFTY", timestamp: datetime | None = None) -> Candle:
    return Candle(
        timestamp=timestamp or datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc),
        symbol=symbol,
        timeframe="5m",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )


def _prediction(symbol: str = "NIFTY", timestamp: datetime | None = None) -> Prediction:
    return Prediction(symbol, timestamp or datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc), "BUY", "model", "1")


def test_cross_symbol_prediction_is_rejected(monkeypatch):
    monkeypatch.setattr(pipeline, "generate_signal", lambda *args, **kwargs: TradeSignal("BUY", 100.0, 99.0, 102.0, 2, "ok"))
    monkeypatch.setattr(pipeline, "apply_ml_decision", lambda *args, **kwargs: args[0])

    candle = _candle("NIFTY")
    assert pipeline.generate_ml_signal([candle], _prediction("BANKNIFTY"), 0.9) is None


def test_stale_prediction_is_rejected(monkeypatch):
    monkeypatch.setattr(pipeline, "generate_signal", lambda *args, **kwargs: TradeSignal("BUY", 100.0, 99.0, 102.0, 2, "ok"))
    monkeypatch.setattr(pipeline, "apply_ml_decision", lambda *args, **kwargs: args[0])

    candle = _candle("NIFTY")
    stale = _prediction("NIFTY", datetime(2026, 8, 26, 7, 55, tzinfo=timezone.utc))
    assert pipeline.generate_ml_signal([candle], stale, 0.9) is None


def test_matching_prediction_reaches_ml_decision(monkeypatch):
    candle = _candle("NIFTY")
    signal = TradeSignal("BUY", 100.0, 99.0, 102.0, 2, "ok")
    monkeypatch.setattr(pipeline, "generate_signal", lambda *args, **kwargs: signal)
    seen = {}

    def apply(signal_arg, prediction_arg, confidence_arg, config_arg):
        seen.update(signal=signal_arg, prediction=prediction_arg, confidence=confidence_arg)
        return signal_arg

    monkeypatch.setattr(pipeline, "apply_ml_decision", apply)
    prediction = _prediction("NIFTY", candle.timestamp)

    assert pipeline.generate_ml_signal([candle], prediction, 0.9) is signal
    assert seen["prediction"] is prediction
    assert seen["confidence"] == 0.9
