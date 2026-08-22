from __future__ import annotations

from dataclasses import asdict, dataclass

from app.market_data import Candle


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str


@dataclass(frozen=True)
class FairValueGap:
    index: int
    direction: str
    low: float
    high: float


def swings(candles: list[Candle], lookback: int = 2) -> list[Swing]:
    out: list[Swing] = []
    if len(candles) < lookback * 2 + 1:
        return out
    for i in range(lookback, len(candles) - lookback):
        c = candles[i]
        left = candles[i - lookback:i]
        right = candles[i + 1:i + lookback + 1]
        if all(c.high > x.high for x in left + right):
            out.append(Swing(i, c.high, "HIGH"))
        if all(c.low < x.low for x in left + right):
            out.append(Swing(i, c.low, "LOW"))
    return out


def fair_value_gaps(candles: list[Candle]) -> list[FairValueGap]:
    out: list[FairValueGap] = []
    for i in range(2, len(candles)):
        a, c = candles[i - 2], candles[i]
        if c.low > a.high:
            out.append(FairValueGap(i, "BULLISH", a.high, c.low))
        elif c.high < a.low:
            out.append(FairValueGap(i, "BEARISH", c.high, a.low))
    return out


def structure(candles: list[Candle]) -> dict:
    sw = swings(candles)
    highs = [x for x in sw if x.kind == "HIGH"]
    lows = [x for x in sw if x.kind == "LOW"]
    bos = None
    choch = None
    if len(highs) >= 2 and len(lows) >= 2:
        last_high, prev_high = highs[-1], highs[-2]
        last_low, prev_low = lows[-1], lows[-2]
        if last_high.price > prev_high.price and last_low.price > prev_low.price:
            bos = "BULLISH"
        elif last_high.price < prev_high.price and last_low.price < prev_low.price:
            bos = "BEARISH"
        if len(sw) >= 3:
            prev_bias = "BULLISH" if prev_high.price > highs[-3].price else "BEARISH"
            if bos and bos != prev_bias:
                choch = bos
    return {
        "bias": bos,
        "bos": bos,
        "choch": choch,
        "swings": [asdict(x) for x in sw],
        "fvg": [asdict(x) for x in fair_value_gaps(candles)],
    }
