from __future__ import annotations
from app.ict_smc import analyze
from app.market_data import Candle


def multi_timeframe_analysis(frames: dict[str, list[Candle]]) -> dict:
    results = {tf: analyze(candles) for tf, candles in frames.items() if len(candles) >= 20}
    if not results:
        raise ValueError("at least one timeframe with 20 candles is required")
    bullish = sum(1 for x in results.values() if x["bias"] == "BULLISH")
    bearish = sum(1 for x in results.values() if x["bias"] == "BEARISH")
    bias = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "NEUTRAL"
    return {"bias": bias, "bullish_timeframes": bullish, "bearish_timeframes": bearish, "timeframes": results}
