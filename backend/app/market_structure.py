from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.market_context import Candle, StructureSnapshot


@dataclass(frozen=True)
class StructureConfig:
    pivot_left: int = 2
    pivot_right: int = 2
    sweep_lookback: int = 20


class MarketStructureEngine:
    """Deterministic swing/BOS/CHOCH/liquidity analysis for a candle series."""

    def __init__(self, config: StructureConfig | None = None):
        self.config = config or StructureConfig()
        if self.config.pivot_left < 1 or self.config.pivot_right < 1:
            raise ValueError("pivot widths must be positive")

    def _pivots(self, candles: Sequence[Candle]):
        highs: list[tuple[int, float]] = []
        lows: list[tuple[int, float]] = []
        l, r = self.config.pivot_left, self.config.pivot_right
        for i in range(l, len(candles) - r):
            h = candles[i].high
            lo = candles[i].low
            if all(h > candles[j].high for j in range(i-l, i) if j >= 0) and all(h >= candles[j].high for j in range(i+1, i+r+1)):
                highs.append((i, h))
            if all(lo < candles[j].low for j in range(i-l, i) if j >= 0) and all(lo <= candles[j].low for j in range(i+1, i+r+1)):
                lows.append((i, lo))
        return highs, lows

    def analyze(self, candles: Sequence[Candle]) -> StructureSnapshot:
        if not candles:
            raise ValueError("candles are required")
        highs, lows = self._pivots(candles)
        swing_high = highs[-1][1] if highs else None
        swing_low = lows[-1][1] if lows else None
        trend = "UNKNOWN"
        if len(highs) >= 2 and len(lows) >= 2:
            hh = highs[-1][1] > highs[-2][1]
            hl = lows[-1][1] > lows[-2][1]
            lh = highs[-1][1] < highs[-2][1]
            ll = lows[-1][1] < lows[-2][1]
            if hh and hl: trend = "BULLISH"
            elif lh and ll: trend = "BEARISH"
            else: trend = "RANGING"

        close = candles[-1].close
        bos = None
        choch = None
        if swing_high is not None and close > swing_high:
            bos = "BULLISH"
            if trend == "BEARISH": choch = "BULLISH"
        elif swing_low is not None and close < swing_low:
            bos = "BEARISH"
            if trend == "BULLISH": choch = "BEARISH"

        recent = candles[-self.config.sweep_lookback:]
        prior_high = max((c.high for c in recent[:-1]), default=None)
        prior_low = min((c.low for c in recent[:-1]), default=None)
        last = candles[-1]
        liquidity_sweep = None
        if prior_high is not None and last.high > prior_high and last.close < prior_high:
            liquidity_sweep = "HIGH"
        elif prior_low is not None and last.low < prior_low and last.close > prior_low:
            liquidity_sweep = "LOW"

        return StructureSnapshot(
            trend=trend,
            swing_high=swing_high,
            swing_low=swing_low,
            bos=bos,
            choch=choch,
            liquidity_sweep=liquidity_sweep,
        )
