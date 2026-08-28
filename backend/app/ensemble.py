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


def decide(candles: list[Candle], *, confluence_weight: float = 0.0) -> EnsembleDecision:
    """Legacy-compatible ensemble with optional confluence evidence.

    The default preserves existing API behavior. A configured weight blends the
    normalized confluence score into the existing AI/technical ensemble.
    """
    if not 0.0 <= confluence_weight <= 1.0:
        raise ValueError("confluence_weight must be between 0 and 1")

    ai = predict(candles)
    technical = score(candles)
    technical_norm = max(-1.0, min(1.0, technical["score"] / 5.0))
    ai_norm = ai.probability_up * 2 - 1
    regime_factor = 0.75 if ai.regime == "HIGH_VOLATILITY" else 1.0
    base_combined = (0.55 * ai_norm + 0.45 * technical_norm) * regime_factor

    reasons = [
        f"AI regime: {ai.regime}",
        f"AI up probability: {ai.probability_up:.2%}",
        f"technical bias: {technical['bias']}",
    ]
    reasons.extend(technical.get("reasons", []))

    if confluence_weight:
        # app.confluence.score returns a bounded technical/SMC evidence score.
        confluence_raw = float(technical.get("score", 0.0))
        confluence_norm = max(-1.0, min(1.0, confluence_raw / 5.0))
        combined = (1.0 - confluence_weight) * base_combined + confluence_weight * confluence_norm
        reasons.append(f"confluence weight: {confluence_weight:.2f}")
        reasons.append(f"confluence normalized score: {confluence_norm:.2f}")
    else:
        combined = base_combined

    if combined >= 0.35:
        action = "BUY"
    elif combined <= -0.35:
        action = "SELL"
    else:
        action = "NO_TRADE"

    return EnsembleDecision(
        action,
        combined,
        abs(combined),
        ai.probability_up,
        technical["score"],
        ai.regime,
        reasons,
    )
