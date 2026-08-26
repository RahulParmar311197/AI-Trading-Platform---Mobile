from __future__ import annotations

from math import sqrt
from typing import Any, Mapping, Sequence


def _closes(candles: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(c["close"]) for c in candles]


def _highs(candles: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(c["high"]) for c in candles]


def _lows(candles: Sequence[Mapping[str, Any]]) -> list[float]:
    return [float(c["low"]) for c in candles]


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(candles: Sequence[Mapping[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    highs, lows, closes = _highs(candles), _lows(candles), _closes(candles)
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(candles))]
    value = sum(trs[:period]) / period
    for tr in trs[period:]:
        value = ((period - 1) * value + tr) / period
    return value


def _adx(candles: Sequence[Mapping[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period * 2:
        return None
    highs, lows, closes = _highs(candles), _lows(candles), _closes(candles)
    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, len(candles)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    atr = sum(trs[:period]) / period
    p = sum(plus_dm[:period]) / period
    m = sum(minus_dm[:period]) / period
    dx = []
    for i in range(period, len(trs)):
        atr = ((period - 1) * atr + trs[i]) / period
        p = ((period - 1) * p + plus_dm[i]) / period
        m = ((period - 1) * m + minus_dm[i]) / period
        plus_di = 100.0 * p / atr if atr else 0.0
        minus_di = 100.0 * m / atr if atr else 0.0
        total = plus_di + minus_di
        dx.append(100.0 * abs(plus_di - minus_di) / total if total else 0.0)
    if len(dx) < period:
        return None
    return sum(dx[:period]) / period


def calculate_indicators(candles: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
    """Calculate the indicators required by the canonical AI decision engine."""
    closes = _closes(candles)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_histogram = None
    if ema12 is not None and ema26 is not None:
        # A signal EMA requires a MACD history; use the current MACD minus
        # its short rolling mean as a deterministic, dependency-free proxy.
        macd_values: list[float] = []
        for end in range(26, len(closes) + 1):
            fast = _ema(closes[:end], 12)
            slow = _ema(closes[:end], 26)
            if fast is not None and slow is not None:
                macd_values.append(fast - slow)
        signal = _ema(macd_values, 9)
        macd_histogram = (ema12 - ema26) - signal if signal is not None else ema12 - ema26
    return {
        "ema_20": _ema(closes, 20),
        "ema_50": _ema(closes, 50),
        "rsi_14": _rsi(closes, 14),
        "macd_histogram": macd_histogram,
        "adx_14": _adx(candles, 14),
        "atr_14": _atr(candles, 14),
    }
