from __future__ import annotations

from dataclasses import dataclass

from app.confluence import score
from app.market_data import Candle


@dataclass(frozen=True)
class TradeSignal:
    action: str
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    reason: list[str]


def generate_signal(candles: list[Candle], min_score: int = 2) -> TradeSignal | None:
    if len(candles) < 20:
        return None
    result = score(candles)
    last = candles[-1].close
    a = result.get("atr") or (candles[-1].high - candles[-1].low)
    if not a or result["score"] < min_score and result["score"] > -min_score:
        return None
    if result["bias"] == "BULLISH":
        entry, stop, target = last, last - 1.5 * a, last + 3 * a
        action = "BUY"
    elif result["bias"] == "BEARISH":
        entry, stop, target = last, last + 1.5 * a, last - 3 * a
        action = "SELL"
    else:
        return None
    risk = abs(entry - stop)
    reward = abs(target - entry)
    confidence = min(0.99, 0.5 + abs(result["score"]) * 0.09)
    return TradeSignal(action, entry, stop, target, reward / risk if risk else 0, confidence, result["reasons"])
