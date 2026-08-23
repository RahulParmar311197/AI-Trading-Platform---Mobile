from dataclasses import dataclass
import pandas as pd

@dataclass
class Swing:
    index: int
    price: float
    kind: str


def detect_swings(df: pd.DataFrame, length: int = 3) -> list[Swing]:
    if len(df) < length * 2 + 1:
        return []
    out: list[Swing] = []
    for i in range(length, len(df) - length):
        h = float(df.iloc[i].high); l = float(df.iloc[i].low)
        left = df.iloc[i-length:i]; right = df.iloc[i+1:i+length+1]
        if h >= float(left.high.max()) and h >= float(right.high.max()):
            out.append(Swing(i, h, "HIGH"))
        if l <= float(left.low.min()) and l <= float(right.low.min()):
            out.append(Swing(i, l, "LOW"))
    return out


def analyze(df: pd.DataFrame, swing_length: int = 3) -> dict:
    swings = detect_swings(df, swing_length)
    if not swings:
        return {"bias":"NEUTRAL","bos":False,"mss":False,"liquidity_sweep":False,"fvg":False,"order_block":False,"score":0,"swings":[]}
    highs = [s for s in swings if s.kind == "HIGH"]
    lows = [s for s in swings if s.kind == "LOW"]
    close = float(df.iloc[-1].close)
    bos_bull = bool(highs and close > highs[-1].price)
    bos_bear = bool(lows and close < lows[-1].price)
    fvg_bull = len(df) >= 3 and float(df.iloc[-1].low) > float(df.iloc[-3].high)
    fvg_bear = len(df) >= 3 and float(df.iloc[-1].high) < float(df.iloc[-3].low)
    sweep_low = bool(lows and float(df.iloc[-1].low) < lows[-1].price and close > lows[-1].price)
    sweep_high = bool(highs and float(df.iloc[-1].high) > highs[-1].price and close < highs[-1].price)
    bull = bos_bull or fvg_bull or sweep_low
    bear = bos_bear or fvg_bear or sweep_high
    bias = "BULLISH" if bull and not bear else "BEARISH" if bear and not bull else "NEUTRAL"
    score = min(100, 25 * sum([bos_bull or bos_bear, fvg_bull or fvg_bear, sweep_low or sweep_high, bias != "NEUTRAL"]))
    return {"bias":bias,"bos":bos_bull or bos_bear,"mss":sweep_low or sweep_high,"liquidity_sweep":sweep_low or sweep_high,"fvg":fvg_bull or fvg_bear,"order_block":False,"score":score,"swings":[s.__dict__ for s in swings[-20:]]}
