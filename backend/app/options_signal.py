from __future__ import annotations

from dataclasses import dataclass

from app.options_chain import OptionQuote, chain_summary


@dataclass(frozen=True)
class OptionsSignal:
    action: str
    score: float
    confidence: float
    bias: str
    reasons: list[str]


def generate_signal(quotes: list[OptionQuote], underlying_bias: str = "NEUTRAL") -> OptionsSignal:
    if not quotes:
        raise ValueError("at least one option quote is required")
    bias = underlying_bias.upper()
    if bias not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        raise ValueError("underlying_bias must be BULLISH, BEARISH, or NEUTRAL")

    summary = chain_summary(quotes)
    score = 0.0
    reasons: list[str] = []

    pcr = summary["put_call_oi_ratio"]
    volume_pcr = summary["put_call_volume_ratio"]
    if pcr is not None:
        if pcr >= 1.2:
            score += 0.30
            reasons.append("put OI dominates call OI")
        elif pcr <= 0.8:
            score -= 0.30
            reasons.append("call OI dominates put OI")
    if volume_pcr is not None:
        if volume_pcr >= 1.2:
            score += 0.20
            reasons.append("put volume dominates call volume")
        elif volume_pcr <= 0.8:
            score -= 0.20
            reasons.append("call volume dominates put volume")

    if bias == "BULLISH":
        score += 0.50
        reasons.append("underlying trend is bullish")
    elif bias == "BEARISH":
        score -= 0.50
        reasons.append("underlying trend is bearish")
    else:
        reasons.append("underlying trend is neutral")

    score = max(-1.0, min(1.0, score))
    if score >= 0.45:
        action = "BUY_CALL"
    elif score <= -0.45:
        action = "BUY_PUT"
    else:
        action = "NO_TRADE"
    return OptionsSignal(action, score, abs(score), "BULLISH" if score > 0.15 else "BEARISH" if score < -0.15 else "NEUTRAL", reasons)
