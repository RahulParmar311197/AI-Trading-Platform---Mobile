from __future__ import annotations

from dataclasses import dataclass

from app.ai_model import predict
from app.confluence import score
from app.market_data import Candle


@dataclass(frozen=True)
class EnsembleDecision:
    action: str
    score: float
    confidence: float
    ai_probability_up: float
    technical_score: float
    regime: str
    reasons: list[str]


def decide(candles: list[Candle]) -> EnsembleDecision:
    ai = predict(candles)
    technical = score(candles)
    technical_norm = max(-1.0, min(1.0, technical["score"] / 5.0))
    ai_norm = ai.probability_up * 2 - 1
    regime_factor = 0.75 if ai.regime == "HIGH_VOLATILITY" else 1.0
    combined = (0.55 * ai_norm + 0.45 * technical_norm) * regime_factor
    if combined >= 0.35:
        action = "BUY"
    elif combined <= -0.35:
        action = "SELL"
    else:
        action = "NO_TRADE"
    reasons = [f"AI regime: {ai.regime}", f"AI up probability: {ai.probability_up:.2%}", f"technical bias: {technical['bias']}"]
    reasons.extend(technical.get("reasons", []))
    return EnsembleDecision(action, combined, abs(combined), ai.probability_up, technical["score"], ai.regime, reasons)
