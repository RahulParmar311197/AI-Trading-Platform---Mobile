from __future__ import annotations

from dataclasses import dataclass

from app.market_data import Candle


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str


@dataclass(frozen=True)
class StructureEvent:
    index: int
    kind: str
    level: float


@dataclass(frozen=True)
class FairValueGap:
    index: int
    direction: str
    low: float
    high: float


@dataclass(frozen=True)
class OrderBlock:
    index: int
    direction: str
    low: float
    high: float


class SMCICTEngine:
    """Streaming-friendly SMC/ICT structure engine without look-ahead bias."""

    def swings(self, candles: list[Candle], lookback: int = 2) -> list[Swing]:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        if not candles:
            return []
        out: list[Swing] = []
        for i in range(lookback, len(candles)):
            current = candles[i]
            previous = candles[i - lookback:i]
            if current.high > max(x.high for x in previous):
                out.append(Swing(i, current.high, "HIGH"))
            if current.low < min(x.low for x in previous):
                out.append(Swing(i, current.low, "LOW"))
        return out

    def structure(self, candles: list[Candle], lookback: int = 2) -> list[StructureEvent]:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        if len(candles) <= lookback:
            return []

        swings = self.swings(candles, lookback)
        highs = [s for s in swings if s.kind == "HIGH"]
        lows = [s for s in swings if s.kind == "LOW"]
        events: list[StructureEvent] = []
        broken_high: set[int] = set()
        broken_low: set[int] = set()

        for i, candle in enumerate(candles):
            prior_highs = [s for s in highs if s.index < i]
            prior_lows = [s for s in lows if s.index < i]
            if prior_highs:
                high = prior_highs[-1]
                if candle.close > high.price and high.index not in broken_high:
                    events.append(StructureEvent(i, "BOS_BULLISH", high.price))
                    broken_high.add(high.index)
            if prior_lows:
                low = prior_lows[-1]
                if candle.close < low.price and low.index not in broken_low:
                    events.append(StructureEvent(i, "BOS_BEARISH", low.price))
                    broken_low.add(low.index)
        return events

    def fair_value_gaps(self, candles: list[Candle]) -> list[FairValueGap]:
        out: list[FairValueGap] = []
        for i in range(2, len(candles)):
            first, _, third = candles[i - 2:i + 1]
            if first.high < third.low:
                out.append(FairValueGap(i, "BULLISH", first.high, third.low))
            if first.low > third.high:
                out.append(FairValueGap(i, "BEARISH", third.high, first.low))
        return out

    def order_blocks(self, candles: list[Candle]) -> list[OrderBlock]:
        out: list[OrderBlock] = []
        for i in range(1, len(candles)):
            previous, current = candles[i - 1], candles[i]
            if current.close > current.open and previous.close < previous.open and current.close > previous.high:
                out.append(OrderBlock(i, "BULLISH", previous.low, previous.high))
            if current.close < current.open and previous.close > previous.open and current.close < previous.low:
                out.append(OrderBlock(i, "BEARISH", previous.low, previous.high))
        return out

    def analyze(self, candles: list[Candle]) -> dict:
        if not candles:
            return {"bias": "NEUTRAL", "score": 0, "swings": [], "structure": [], "fair_value_gaps": [], "order_blocks": []}
        swings = self.swings(candles)
        structure = self.structure(candles)
        gaps = self.fair_value_gaps(candles)
        blocks = self.order_blocks(candles)
        bull = sum(x.kind == "BOS_BULLISH" for x in structure) + sum(x.direction == "BULLISH" for x in gaps) + sum(x.direction == "BULLISH" for x in blocks)
        bear = sum(x.kind == "BOS_BEARISH" for x in structure) + sum(x.direction == "BEARISH" for x in gaps) + sum(x.direction == "BEARISH" for x in blocks)
        return {"bias": "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL", "score": bull - bear, "swings": swings, "structure": structure, "fair_value_gaps": gaps, "order_blocks": blocks}
