from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from app.market_data import Candle, validate_candle_sequence


@dataclass(frozen=True)
class TechnicalSnapshot:
    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    macd: float | None
    atr: float | None
    adx: float | None
    vwap: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    trend: str
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_9: float | None = None
    ema_20: float | None = None
    ema_50: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bollinger_middle: float | None = None
    volume: float | None = None


class TechnicalAnalysisEngine:
    def _closes(self, candles: list[Candle]) -> list[float]:
        return [float(x.close) for x in candles]

    def _period(self, period: int) -> int:
        if period < 1:
            raise ValueError("period must be positive")
        return period

    def sma(self, values: list[float], period: int) -> float | None:
        period = self._period(period)
        return sum(values[-period:]) / period if len(values) >= period else None

    def ema(self, values: list[float], period: int) -> float | None:
        period = self._period(period)
        if len(values) < period:
            return None
        e = sum(values[:period]) / period
        a = 2 / (period + 1)
        for v in values[period:]:
            e = (v - e) * a + e
        return e

    def rsi(self, values: list[float], period: int = 14) -> float | None:
        period = self._period(period)
        if len(values) < period + 1:
            return None
        gains = [max(values[i] - values[i - 1], 0) for i in range(1, len(values))]
        losses = [max(values[i - 1] - values[i], 0) for i in range(1, len(values))]
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        for g, l in zip(gains[period:], losses[period:]):
            ag = (ag * (period - 1) + g) / period
            al = (al * (period - 1) + l) / period
        return 100.0 if al == 0 else 100 - (100 / (1 + ag / al))

    def atr(self, candles: list[Candle], period: int = 14) -> float | None:
        period = self._period(period)
        if len(candles) < period + 1:
            return None
        tr = []
        for i in range(1, len(candles)):
            c, p = candles[i], candles[i - 1]
            tr.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
        return sum(tr[-period:]) / period

    def adx(self, candles: list[Candle], period: int = 14) -> float | None:
        period = self._period(period)
        if len(candles) < period + 1:
            return None
        tr, plus, minus = [], [], []
        for i in range(1, len(candles)):
            c, p = candles[i], candles[i - 1]
            tr.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
            up = c.high - p.high
            down = p.low - c.low
            plus.append(up if up > down and up > 0 else 0)
            minus.append(down if down > up and down > 0 else 0)
        t = sum(tr[-period:]) / period
        if not t:
            return 0.0
        pdi = 100 * (sum(plus[-period:]) / period) / t
        mdi = 100 * (sum(minus[-period:]) / period) / t
        den = pdi + mdi
        return 100 * abs(pdi - mdi) / den if den else 0.0

    def vwap(self, candles: list[Candle]) -> float | None:
        if not candles:
            return None
        tv = sum(((c.high + c.low + c.close) / 3) * max(c.volume, 0) for c in candles)
        vol = sum(max(c.volume, 0) for c in candles)
        return tv / vol if vol else None

    def bollinger(self, values: list[float], period: int = 20, k: float = 2) -> tuple[float | None, float | None, float | None]:
        period = self._period(period)
        if not isfinite(k) or k < 0:
            raise ValueError("bollinger deviation multiplier must be finite and non-negative")
        if len(values) < period:
            return None, None, None
        w = values[-period:]
        m = sum(w) / period
        sd = sqrt(sum((x - m) ** 2 for x in w) / period)
        return m + k * sd, m, m - k * sd

    def macd_values(self, values: list[float]) -> tuple[float | None, float | None, float | None]:
        fast = self.ema(values, 12)
        slow = self.ema(values, 26)
        if fast is None or slow is None:
            return None, None, None
        series = []
        for i in range(25, len(values)):
            f = self.ema(values[: i + 1], 12)
            s = self.ema(values[: i + 1], 26)
            if f is not None and s is not None:
                series.append(f - s)
        signal = self.ema(series, 9) if len(series) >= 9 else None
        line = series[-1] if series else fast - slow
        hist = line - signal if signal is not None else None
        return line, signal, hist

    def snapshot(self, candles: list[Candle]) -> TechnicalSnapshot:
        if not candles:
            raise ValueError("at least one canonical candle is required")
        if not validate_candle_sequence(candles):
            raise ValueError("invalid candle sequence for technical analysis")

        v = self._closes(candles)
        fast = self.ema(v, 12)
        slow = self.ema(v, 26)
        upper, middle, lower = self.bollinger(v)
        macd, signal, hist = self.macd_values(v)
        r = self.rsi(v)
        a = self.atr(candles)
        adx = self.adx(candles)
        vw = self.vwap(candles)
        s20 = self.sma(v, 20)
        s50 = self.sma(v, 50)
        s200 = self.sma(v, 200)
        e9 = self.ema(v, 9)
        e20 = self.ema(v, 20)
        e50 = self.ema(v, 50)
        trend = "BULLISH" if fast is not None and slow is not None and fast > slow else "BEARISH" if fast is not None and slow is not None else "NEUTRAL"
        return TechnicalSnapshot(
            fast, slow, r, macd, a, adx, vw, upper, lower, trend,
            s20, s50, s200, e9, e20, e50, signal, hist, middle, candles[-1].volume,
        )
