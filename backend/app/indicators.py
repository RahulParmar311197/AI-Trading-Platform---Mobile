from __future__ import annotations

from math import sqrt


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    alpha = 2 / (period + 1)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = alpha * value + (1 - alpha) * result
    return result


def true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    if not high or len(high) != len(low) or len(high) != len(close):
        return []
    out = [high[0] - low[0]]
    for i in range(1, len(high)):
        out.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return out


def atr(high: list[float], low: list[float], close: list[float], period: int = 14) -> float | None:
    tr = true_range(high, low, close)
    return sma(tr, period)


def volatility(values: list[float], period: int = 20) -> float | None:
    if len(values) < period or period <= 1:
        return None
    window = values[-period:]
    mean = sum(window) / period
    return sqrt(sum((x - mean) ** 2 for x in window) / (period - 1))
