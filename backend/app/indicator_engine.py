from __future__ import annotations

from dataclasses import dataclass
import math

from app.market_context import Candle, IndicatorSnapshot


def _finite(values):
    return all(math.isfinite(float(v)) for v in values)


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period or not _finite(values):
        return None
    value = sum(values[:period]) / period
    alpha = 2.0 / (period + 1)
    for price in values[period:]:
        value = alpha * price + (1 - alpha) * value
    return value


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1 or not _finite(values):
        return None
    gains = []
    losses = []
    for a, b in zip(values[-(period + 1):-1], values[-period:]):
        delta = b - a
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs = []
    for previous, current in zip(candles[-(period + 1):-1], candles[-period:]):
        trs.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    return sum(trs) / period


def _adx(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    tr = []
    plus_dm = []
    minus_dm = []
    for previous, current in zip(candles[-(period + 1):-1], candles[-period:]):
        up = current.high - previous.high
        down = previous.low - current.low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    tr_sum = sum(tr)
    if tr_sum <= 0:
        return None
    plus_di = 100.0 * sum(plus_dm) / tr_sum
    minus_di = 100.0 * sum(minus_dm) / tr_sum
    denominator = plus_di + minus_di
    return 100.0 * abs(plus_di - minus_di) / denominator if denominator else 0.0


def calculate_indicators(candles: list[Candle] | tuple[Candle, ...]) -> IndicatorSnapshot:
    """Calculate the canonical indicators consumed by AIDecisionEngine."""
    series = list(candles)
    closes = [float(c.close) for c in series]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    # MACD histogram requires the 9-period EMA of the MACD series.
    macd_hist = None
    if len(closes) >= 35 and _finite(closes):
        macd_values = []
        for i in range(26, len(closes) + 1):
            fast_i = _ema(closes[:i], 12)
            slow_i = _ema(closes[:i], 26)
            if fast_i is not None and slow_i is not None:
                macd_values.append(fast_i - slow_i)
        signal = _ema(macd_values, 9)
        if signal is not None:
            macd_hist = macd_values[-1] - signal
    values = {
        "ema_20": ema20,
        "ema_50": ema50,
        "rsi_14": _rsi(closes, 14),
        "macd_histogram": macd_hist,
        "atr_14": _atr(series, 14),
        "adx_14": _adx(series, 14),
    }
    return IndicatorSnapshot(values=values)
