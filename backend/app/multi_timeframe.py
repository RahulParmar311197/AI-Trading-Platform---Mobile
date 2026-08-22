from __future__ import annotations

from app.confluence import score
from app.market_data import market_data


def analyze(symbol: str, timeframes: list[str] | None = None, limit: int = 500) -> dict:
    timeframes = timeframes or ["15m", "1h", "4h"]
    frames = []
    weighted = 0.0
    total_weight = 0.0
    for index, timeframe in enumerate(timeframes):
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        result = score(candles) if len(candles) >= 20 else {"score": 0, "bias": "NEUTRAL", "reasons": [], "atr": None}
        weight = index + 1
        weighted += result["score"] * weight
        total_weight += weight
        frames.append({"timeframe": timeframe, "score": result["score"], "bias": result["bias"], "reasons": result["reasons"]})
    composite = weighted / total_weight if total_weight else 0
    bias = "BULLISH" if composite >= 1.5 else "BEARISH" if composite <= -1.5 else "NEUTRAL"
    return {"symbol": symbol.upper(), "bias": bias, "composite_score": round(composite, 3), "timeframes": frames}
