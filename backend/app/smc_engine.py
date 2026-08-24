from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.market_context import Candle, SMCSnapshot


@dataclass(frozen=True)
class SMCConfig:
    fvg_min_atr_fraction: float = 0.10
    equal_tolerance_fraction: float = 0.001
    dealing_range_lookback: int = 50


class SMCEngine:
    """Deterministic SMC feature extraction. Signals are evidence, not trade commands."""

    def __init__(self, config: SMCConfig | None = None):
        self.config = config or SMCConfig()
        if self.config.fvg_min_atr_fraction < 0 or self.config.equal_tolerance_fraction < 0:
            raise ValueError("SMC thresholds must be non-negative")

    @staticmethod
    def _atr(candles: Sequence[Candle], period: int = 14) -> float:
        if not candles: return 0.0
        trs=[]
        for i,c in enumerate(candles):
            prev=candles[i-1].close if i else c.open
            trs.append(max(c.high-c.low, abs(c.high-prev), abs(c.low-prev)))
        return sum(trs[-period:])/min(period,len(trs))

    def _order_blocks(self, candles: Sequence[Candle]) -> list[dict[str, Any]]:
        blocks=[]
        for i in range(1,len(candles)):
            prev,c=candles[i-1],candles[i]
            bullish_displacement=c.close > prev.high and c.close > c.open
            bearish_displacement=c.close < prev.low and c.close < c.open
            if bullish_displacement and prev.close < prev.open:
                blocks.append({"index":i-1,"type":"BULLISH","high":prev.high,"low":prev.low})
            elif bearish_displacement and prev.close > prev.open:
                blocks.append({"index":i-1,"type":"BEARISH","high":prev.high,"low":prev.low})
        return blocks[-10:]

    def _fvgs(self, candles: Sequence[Candle]) -> list[dict[str, Any]]:
        threshold=self._atr(candles)*self.config.fvg_min_atr_fraction
        gaps=[]
        for i in range(2,len(candles)):
            first,middle,last=candles[i-2],candles[i-1],candles[i]
            if last.low > first.high and last.low-first.high >= threshold:
                gaps.append({"index":i,"type":"BULLISH","high":last.low,"low":first.high})
            elif last.high < first.low and first.low-last.high >= threshold:
                gaps.append({"index":i,"type":"BEARISH","high":first.low,"low":last.high})
        return gaps[-10:]

    def _equal_levels(self, candles: Sequence[Candle]) -> tuple[list[float],list[float]]:
        tolerance=self.config.equal_tolerance_fraction
        highs=[]; lows=[]
        for i in range(1,len(candles)):
            for j in range(i):
                if abs(candles[i].high-candles[j].high)/max(abs(candles[i].high),1e-9) <= tolerance: highs.append(candles[i].high); break
            for j in range(i):
                if abs(candles[i].low-candles[j].low)/max(abs(candles[i].low),1e-9) <= tolerance: lows.append(candles[i].low); break
        return highs[-10:], lows[-10:]

    def analyze(self, candles: Sequence[Candle]) -> SMCSnapshot:
        if not candles: raise ValueError("candles are required")
        window=candles[-self.config.dealing_range_lookback:]
        high=max(c.high for c in window); low=min(c.low for c in window); midpoint=(high+low)/2
        close=candles[-1].close
        premium_discount="PREMIUM" if close > midpoint else "DISCOUNT" if close < midpoint else "EQUILIBRIUM"
        equal_highs,equal_lows=self._equal_levels(window)
        return SMCSnapshot(order_blocks=self._order_blocks(window),fair_value_gaps=self._fvgs(window),premium_discount=premium_discount,equal_highs=equal_highs,equal_lows=equal_lows)
