from __future__ import annotations

from app.confluence import score
from app.market_data import market_data

TIMEFRAME_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
DEFAULT_TIMEFRAMES = ("15m", "1h", "4h")
CONTEXT_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")


def _validate_timeframes(timeframes: list[str] | None, defaults: tuple[str, ...]) -> list[str]:
    values = list(timeframes or defaults)
    if not values:
        raise ValueError("at least one timeframe is required")
    if len(set(values)) != len(values):
        raise ValueError("duplicate timeframes are not allowed")
    unsupported = [tf for tf in values if tf not in TIMEFRAME_MINUTES]
    if unsupported:
        raise ValueError(f"unsupported timeframe: {unsupported[0]}")
    return values


def analyze(symbol: str, timeframes: list[str] | None = None, limit: int = 500) -> dict:
    if limit <= 0:
        raise ValueError("limit must be positive")
    frames = _validate_timeframes(timeframes, DEFAULT_TIMEFRAMES)
    weighted = 0.0
    total_weight = 0.0
    details = []
    for index, timeframe in enumerate(frames):
        candles = market_data.candles(symbol, timeframe, min(limit, 5000))
        result = score(candles) if len(candles) >= 20 else {"score": 0, "bias": "NEUTRAL", "reasons": [], "atr": None}
        weight = index + 1
        weighted += result["score"] * weight
        total_weight += weight
        details.append({"timeframe": timeframe, "score": result["score"], "bias": result["bias"], "reasons": result["reasons"]})
    composite = weighted / total_weight
    bias = "BULLISH" if composite >= 1.5 else "BEARISH" if composite <= -1.5 else "NEUTRAL"
    return {"symbol": symbol.strip().upper(), "bias": bias, "composite_score": round(composite, 3), "timeframes": details}


def latest_context(symbol: str, timeframes: list[str] | None = None) -> dict:
    frames = _validate_timeframes(timeframes, CONTEXT_TIMEFRAMES)
    result = {}
    for timeframe in frames:
        candles = market_data.candles(symbol, timeframe, 1)
        result[timeframe] = candles[-1] if candles else None
    return result
