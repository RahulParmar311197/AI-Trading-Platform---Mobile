from __future__ import annotations

from math import isfinite
from app.market_data import Candle


def _ema(values: list[float], period: int) -> float:
    if not values: return 0.0
    k = 2 / (period + 1)
    value = values[0]
    for x in values[1:]: value = x * k + value * (1 - k)
    return value


def build_features(candles: list[Candle]) -> dict:
    if len(candles) < 30: raise ValueError("at least 30 candles required")
    closes = [c.close for c in candles]
    ranges = [c.high - c.low for c in candles]
    returns = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
    last = candles[-1]
    atr = sum(ranges[-14:]) / 14
    mean_return = sum(returns[-20:]) / 20
    volatility = (sum((x - mean_return) ** 2 for x in returns[-20:]) / 20) ** 0.5
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    return {
        "close": last.close,
        "ema20": ema20,
        "ema50": ema50,
        "ema_spread_pct": (ema20 / ema50 - 1) * 100 if ema50 else 0,
        "atr": atr,
        "atr_pct": atr / last.close * 100 if last.close else 0,
        "return_5": closes[-1] / closes[-6] - 1,
        "return_20": closes[-1] / closes[-21] - 1,
        "volatility_20": volatility,
        "range_position": (last.close - last.low) / (last.high - last.low) if last.high != last.low else 0.5,
        "volume": getattr(last, "volume", 0),
    }
