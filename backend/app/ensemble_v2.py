from __future__ import annotations

from dataclasses import dataclass

from app.ai_model import predict
from app.confluence import score as technical_score
from app.ict_engine import structure
from app.ict_zones import analyze_zones
from app.market_data import Candle


@dataclass(frozen=True)
class EnsembleV2Decision:
    action: str
    score: float
    confidence: float
    ai_probability_up: float
    technical_score: float
    ict_score: float
    structure_bias: str
    zone_bias: str
    regime: str
    reasons: list[str]


def decide_v2(candles: list[Candle]) -> EnsembleV2Decision:
    if len(candles) < 30:
        raise ValueError("at least 30 candles required")

    ai = predict(candles)
    technical = technical_score(candles)
    ict = structure(candles)
    zones = analyze_zones(candles)

    structure_bias = ict.get("bias") or "NEUTRAL"

    structure_score = (
        2
        if structure_bias == "BULLISH"
        else -2
        if structure_bias == "BEARISH"
        else 0
    )

    ai_norm = ai.probability_up * 2 - 1

    tech_norm = max(
        -1.0,
        min(1.0, technical["score"] / 5.0),
    )

    ict_norm = max(
        -1.0,
        min(
            1.0,
            (structure_score + zones["score"]) / 4.0,
        ),
    )

    regime_factor = (
        0.75
        if ai.regime == "HIGH_VOLATILITY"
        else 1.0
    )

    combined = (
        0.40 * ai_norm
        + 0.25 * tech_norm
        + 0.35 * ict_norm
    ) * regime_factor

    if combined >= 0.35:
        action = "BUY"
    elif combined <= -0.35:
        action = "SELL"
    else:
        action = "NO_TRADE"

    reasons = [
        f"AI regime: {ai.regime}",
        f"AI up probability: {ai.probability_up:.2%}",
        f"technical bias: {technical['bias']}",
        f"structure bias: {structure_bias}",
        f"ICT zone bias: {zones['bias']}",
    ]

    reasons.extend(technical.get("reasons", []))
    reasons.extend(zones.get("reasons", []))

    return EnsembleV2Decision(
        action=action,
        score=combined,
        confidence=abs(combined),
        ai_probability_up=ai.probability_up,
        technical_score=technical["score"],
        ict_score=structure_score + zones["score"],
        structure_bias=structure_bias,
        zone_bias=zones["bias"],
        regime=ai.regime,
        reasons=reasons,
    )