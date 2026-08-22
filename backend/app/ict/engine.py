from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class ICTSignal:
    symbol: str
    bias: str
    score: float
    reasons: list[str]

def analyze_ict(symbol: str, candles: Iterable[dict]) -> ICTSignal:
    rows = list(candles)
    if len(rows) < 5:
        return ICTSignal(symbol, "neutral", 0.0, ["insufficient candles"])
    highs = [float(x["high"]) for x in rows]
    lows = [float(x["low"]) for x in rows]
    closes = [float(x["close"]) for x in rows]
    bullish = closes[-1] > closes[-3] and highs[-1] >= max(highs[-4:-1])
    bearish = closes[-1] < closes[-3] and lows[-1] <= min(lows[-4:-1])
    if bullish and not bearish:
        return ICTSignal(symbol, "bullish", 0.7, ["displacement", "buy-side structure"])
    if bearish and not bullish:
        return ICTSignal(symbol, "bearish", 0.7, ["displacement", "sell-side structure"])
    return ICTSignal(symbol, "neutral", 0.2, ["mixed structure"])
