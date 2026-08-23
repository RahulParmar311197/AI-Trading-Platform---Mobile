from __future__ import annotations

from dataclasses import dataclass
from app.ai_features import build_features
from app.market_data import Candle


@dataclass(frozen=True)
class ModelPrediction:
    probability_up: float
    probability_down: float
    regime: str
    confidence: float
    features: dict


def predict(candles: list[Candle]) -> ModelPrediction:
    f = build_features(candles)
    trend = 0.5
    trend += 0.15 if f["ema20"] > f["ema50"] else -0.15
    trend += min(0.15, max(-0.15, f["return_5"] * 8))
    trend += min(0.10, max(-0.10, f["return_20"] * 3))
    trend += (f["range_position"] - 0.5) * 0.12
    probability_up = min(0.99, max(0.01, trend))
    probability_down = 1 - probability_up
    if f["volatility_20"] > 0.02:
        regime = "HIGH_VOLATILITY"
    elif abs(f["ema_spread_pct"]) < 0.15:
        regime = "RANGE"
    elif probability_up >= 0.6:
        regime = "BULL_TREND"
    elif probability_down >= 0.6:
        regime = "BEAR_TREND"
    else:
        regime = "TRANSITION"
    confidence = abs(probability_up - 0.5) * 2
    return ModelPrediction(probability_up, probability_down, regime, confidence, f)
