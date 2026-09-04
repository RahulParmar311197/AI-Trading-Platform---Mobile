from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite

from app.market_data import Candle, validate_candle_sequence
from app.market_context import ICTSnapshot


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


@dataclass(frozen=True)
class LiquidityPool:
    index: int
    kind: str
    price: float
    tolerance: float


@dataclass(frozen=True)
class OrderBlock:
    index: int
    direction: str
    low: float
    high: float
    displacement: float


def _validated(candles: list[Candle]) -> list[Candle]:
    series = list(candles)
    if not series or not validate_candle_sequence(series):
        raise ValueError("invalid canonical candle sequence for ICT analysis")
    return series


def _positive_int(value: int, name: str) -> int:
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def swings(candles: list[Candle], lookback: int = 2) -> list[Swing]:
    candles = _validated(candles)
    lookback = _positive_int(lookback, "lookback")
    out = []
    for i in range(lookback, len(candles) - lookback):
        c = candles[i]
        around = candles[i - lookback:i] + candles[i + 1:i + lookback + 1]
        if all(c.high > x.high for x in around):
            out.append(Swing(i, c.high, "HIGH"))
        if all(c.low < x.low for x in around):
            out.append(Swing(i, c.low, "LOW"))
    return out


def fair_value_gaps(candles: list[Candle]) -> list[FairValueGap]:
    candles = _validated(candles)
    out = []
    for i in range(2, len(candles)):
        a, c = candles[i - 2], candles[i]
        if c.low > a.high:
            out.append(FairValueGap(i, "BULLISH", a.high, c.low))
        elif c.high < a.low:
            out.append(FairValueGap(i, "BEARISH", c.high, a.low))
    return out


def liquidity_pools(candles: list[Candle], lookback: int = 30, tolerance_bps: float = 5.0) -> list[LiquidityPool]:
    candles = _validated(candles)
    lookback = _positive_int(lookback, "lookback")
    if not isfinite(tolerance_bps) or tolerance_bps < 0:
        raise ValueError("tolerance_bps must be finite and non-negative")
    sw = swings(candles)
    tol = max(1e-12, tolerance_bps / 10000)
    pools = []
    for i, x in enumerate(sw):
        for y in sw[:i]:
            if x.kind == y.kind and abs(x.price - y.price) / max(abs(x.price), 1e-12) <= tol:
                pools.append(LiquidityPool(x.index, "EQUAL_HIGH" if x.kind == "HIGH" else "EQUAL_LOW", (x.price + y.price) / 2, tol))
                break
    return pools[-lookback:]


def liquidity_sweeps(candles: list[Candle], pools: list[LiquidityPool]) -> list[dict]:
    candles = _validated(candles)
    if pools is None:
        raise ValueError("pools are required")
    out = []
    for p in pools:
        if p.kind not in {"EQUAL_HIGH", "EQUAL_LOW"} or not all(isfinite(float(v)) for v in (p.price, p.tolerance)):
            raise ValueError("invalid liquidity pool")
        if p.tolerance < 0:
            raise ValueError("liquidity pool tolerance must be non-negative")
        for i in range(p.index + 1, len(candles)):
            c = candles[i]
            if p.kind == "EQUAL_HIGH" and c.high > p.price and c.close < p.price:
                out.append({"index": i, "direction": "BEARISH", "price": p.price})
            elif p.kind == "EQUAL_LOW" and c.low < p.price and c.close > p.price:
                out.append({"index": i, "direction": "BULLISH", "price": p.price})
    return out


def order_blocks(candles: list[Candle], displacement_mult: float = 1.5) -> list[OrderBlock]:
    candles = _validated(candles)
    if not isfinite(displacement_mult) or displacement_mult <= 0:
        raise ValueError("displacement_mult must be finite and positive")
    if len(candles) < 4:
        return []
    out = []
    for i in range(1, len(candles) - 1):
        prev = candles[i]
        nxt = candles[i + 1]
        rng = max(prev.high - prev.low, 1e-12)
        move = abs(nxt.close - nxt.open)
        if move < displacement_mult * rng:
            continue
        if nxt.close > nxt.open and prev.close < prev.open:
            out.append(OrderBlock(i, "BULLISH", prev.low, prev.high, move / rng))
        elif nxt.close < nxt.open and prev.close > prev.open:
            out.append(OrderBlock(i, "BEARISH", prev.low, prev.high, move / rng))
    return out


def dealing_range(candles: list[Candle]) -> dict:
    candles = _validated(candles)
    sw = swings(candles)
    if not sw:
        return {"high": None, "low": None, "equilibrium": None, "location": "UNKNOWN"}
    hi = max(x.price for x in sw)
    lo = min(x.price for x in sw)
    eq = (hi + lo) / 2
    price = candles[-1].close
    location = "PREMIUM" if price > eq else "DISCOUNT" if price < eq else "EQUILIBRIUM"
    return {"high": hi, "low": lo, "equilibrium": eq, "location": location, "range": hi - lo}


def _session(hour: int) -> str:
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 21:
        return "NEW_YORK"
    return "OFF_SESSION"


def _kill_zone(hour: int) -> str | None:
    if 7 <= hour < 10:
        return "LONDON_OPEN"
    if 13 <= hour < 16:
        return "NEW_YORK_OPEN"
    return None


def ict_context(candles: list[Candle]) -> dict:
    candles = _validated(candles)
    dr = dealing_range(candles)
    hi = dr.get("high")
    lo = dr.get("low")
    span = (hi - lo) if hi is not None and lo is not None else 0
    price = candles[-1].close
    ote_low = lo + span * 0.62 if lo is not None else None
    ote_high = lo + span * 0.79 if lo is not None else None
    target = hi if hi is not None and price < dr.get("equilibrium", price) else lo
    return {
        **dr,
        "session": _session(candles[-1].timestamp.hour),
        "kill_zone": _kill_zone(candles[-1].timestamp.hour),
        "ote_low": ote_low,
        "ote_high": ote_high,
        "ote_mid": ((ote_low + ote_high) / 2 if ote_low is not None else None),
        "liquidity_target": target,
    }


def _choch(highs: list[Swing], lows: list[Swing]) -> str | None:
    if len(highs) < 2 or len(lows) < 2:
        return None
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price
    if ll and highs[-1].price > highs[-2].price:
        return "BULLISH"
    if hh and lows[-1].price < lows[-2].price:
        return "BEARISH"
    if lh and lows[-1].price > lows[-2].price:
        return "BULLISH"
    if hl and highs[-1].price < highs[-2].price:
        return "BEARISH"
    return None


def structure(candles: list[Candle]) -> dict:
    candles = _validated(candles)
    sw = swings(candles)
    highs = [x for x in sw if x.kind == "HIGH"]
    lows = [x for x in sw if x.kind == "LOW"]
    labels = []
    for seq in (highs, lows):
        for n, x in enumerate(seq):
            if n:
                labels.append({
                    "index": x.index,
                    "type": (("HH" if x.price > seq[n - 1].price else "LH") if x.kind == "HIGH" else ("HL" if x.price > seq[n - 1].price else "LL")),
                    "price": x.price,
                })
    labels.sort(key=lambda x: x["index"])
    bos = None
    bias = None
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1].price > highs[-2].price
        hl = lows[-1].price > lows[-2].price
        lh = highs[-1].price < highs[-2].price
        ll = lows[-1].price < lows[-2].price
        if hh and hl:
            bos = bias = "BULLISH"
        elif lh and ll:
            bos = bias = "BEARISH"
    pools = liquidity_pools(candles)
    sweeps = liquidity_sweeps(candles, pools)
    fvg = fair_value_gaps(candles)
    obs = order_blocks(candles)
    return {
        "bias": bias,
        "bos": bos,
        "choch": _choch(highs, lows),
        "swings": [asdict(x) for x in sw],
        "structure_labels": labels,
        "fvg": [asdict(x) for x in fvg],
        "liquidity_pools": [asdict(x) for x in pools],
        "liquidity_sweeps": sweeps,
        "order_blocks": [asdict(x) for x in obs],
        "dealing_range": dealing_range(candles),
        "ict": ict_context(candles),
    }


class ICTEngine:
    """Compatibility facade over the functional ICT analysis API."""

    swings = staticmethod(swings)
    fair_value_gaps = staticmethod(fair_value_gaps)
    liquidity_pools = staticmethod(liquidity_pools)
    liquidity_sweeps = staticmethod(liquidity_sweeps)
    order_blocks = staticmethod(order_blocks)
    dealing_range = staticmethod(dealing_range)
    ict_context = staticmethod(ict_context)
    structure = staticmethod(structure)

    def analyze(self, candles):
        context = ict_context(list(candles))
        return ICTSnapshot(
            dealing_range_high=context.get("high"),
            dealing_range_low=context.get("low"),
            optimal_trade_entry=context.get("ote_mid"),
            session=context.get("session"),
            kill_zone=context.get("kill_zone"),
            liquidity_target=context.get("liquidity_target"),
        )
