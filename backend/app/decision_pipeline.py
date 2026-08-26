from __future__ import annotations
from app.market_data import Candle
from app.strategy import TradeSignal, generate_signal
from app.ml_decision import MLDecisionConfig, apply_ml_decision
from app.ml_inference import Prediction


def generate_ml_signal(
    candles: list[Candle],
    prediction: Prediction,
    ml_confidence: float,
    *,
    min_score: int = 2,
    htf_candles: list[Candle] | None = None,
    require_mtf: bool = False,
    max_age_seconds: float | None = None,
    config: MLDecisionConfig | None = None,
) -> TradeSignal | None:
    """Apply validated ML evidence to the deterministic strategy signal.

    This function only produces a signal. Risk authorization and execution
    remain downstream and are never bypassed by ML.
    """
    signal = generate_signal(
        candles,
        min_score=min_score,
        htf_candles=htf_candles,
        require_mtf=require_mtf,
        max_age_seconds=max_age_seconds,
    )
    if signal is None:
        return None
    return apply_ml_decision(signal, prediction, ml_confidence, config)
