from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str


def swings(candles: list[Candle], strength: int = 2) -> list[Swing]:
    if len(candles) < strength * 2 + 1:
        return []
    out = []
    for i in range(strength, len(candles) - strength):
        left = candles[i-strength:i]
        right = candles[i+1:i+1+strength]
        c = candles[i]
        if all(c.high > x.high for x in left + right):
            out.append(Swing(i, c.high, "HIGH"))
        elif all(c.low < x.low for x in left + right):
            out.append(Swing(i, c.low, "LOW"))
    return out


def analyze(candles: list[Candle]) -> dict:
    if len(candles) < 20:
        raise ValueError("at least 20 candles required")
    sw = swings(candles)
    highs = [x for x in sw if x.kind == "HIGH"]
    lows = [x for x in sw if x.kind == "LOW"]
    last = candles[-1]
    score = 0.0
    reasons = []
    bos = None
    if highs and last.close > highs[-1].price:
        bos = "BULLISH"
        score += 1.0
        reasons.append("break of recent swing high")
    elif lows and last.close < lows[-1].price:
        bos = "BEARISH"
        score -= 1.0
        reasons.append("break of recent swing low")
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
            score += 0.75
            reasons.append("higher-high / higher-low structure")
        elif highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
            score -= 0.75
            reasons.append("lower-high / lower-low structure")
    recent_range = max(last.high - last.low, 1e-9)
    range_position = (last.close - last.low) / recent_range
    if range_position <= 0.25:
        score += 0.25
        reasons.append("discount-side candle")
    elif range_position >= 0.75:
        score -= 0.25
        reasons.append("premium-side candle")
    return {"score": score, "bias": "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL", "bos": bos, "swing_high": highs[-1].price if highs else None, "swing_low": lows[-1].price if lows else None, "range_position": range_position, "reasons": reasons}
