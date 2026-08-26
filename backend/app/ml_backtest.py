from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

from app.decision_pipeline import generate_ml_signal
from app.market_data import Candle
from app.ml_baseline import FEATURE_NAMES
from app.ml_features import build_feature_vector
from app.ml_inference import Prediction, Predictor, predict_one
from app.ml_registry import ModelArtifact

@dataclass(frozen=True)
class BacktestDecision:
    timestamp: object
    symbol: str
    ml_label: str
    strategy_action: str | None
    strategy_confidence: float | None


def run_ml_backtest(
    candles: Sequence[Candle],
    model: Predictor,
    artifact: ModelArtifact,
    *,
    expected_horizon: int = 5,
    expected_threshold: float = 0.002,
    ml_confidence: float = 0.75,
    min_score: int = 2,
) -> list[BacktestDecision]:
    data = sorted(candles, key=lambda c: c.timestamp)
    results: list[BacktestDecision] = []
    for index in range(19, len(data)):
        history = data[: index + 1]
        features = build_feature_vector(history)
        if features is None:
            continue
        prediction = predict_one(
            model, artifact, features, FEATURE_NAMES,
            expected_horizon, expected_threshold,
        )
        signal = generate_ml_signal(
            history, prediction, ml_confidence, min_score=min_score,
        )
        results.append(BacktestDecision(
            timestamp=features.timestamp,
            symbol=features.symbol,
            ml_label=prediction.label,
            strategy_action=signal.action if signal else None,
            strategy_confidence=signal.confidence if signal else None,
        ))
    return results
