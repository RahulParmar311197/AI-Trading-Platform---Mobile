from __future__ import annotations
from dataclasses import asdict, dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class Zone:
    kind: str
    index: int
    high: float
    low: float
    strength: float

def detect_fvg(candles: list[Candle]) -> list[Zone]:
    zones=[]
    for i in range(2,len(candles)):
        a,b,c=candles[i-2],candles[i-1],candles[i]
        if c.low > a.high:
            zones.append(Zone("BULLISH_FVG",i,a.high,c.low,min(1.0,(c.low-a.high)/max(b.high-b.low,1e-9))))
        elif c.high < a.low:
            zones.append(Zone("BEARISH_FVG",i,a.low,c.high,min(1.0,(a.low-c.high)/max(b.high-b.low,1e-9))))
    return zones

def detect_order_blocks(candles: list[Candle], lookback: int=5) -> list[Zone]:
    zones=[]
    for i in range(lookback,len(candles)):
        c=candles[i]; prev=candles[i-lookback:i]
        avg=max(sum(x.high-x.low for x in prev)/lookback,1e-9)
        displacement=(c.high-c.low)/avg
        if displacement>=1.8:
            source=candles[i-1]
            kind="BULLISH_OB" if c.close>c.open else "BEARISH_OB"
            zones.append(Zone(kind,i,source.high,source.low,min(1.0,displacement/4)))
    return zones

def detect_liquidity(candles: list[Candle], tolerance: float=0.001) -> dict:
    highs=[]; lows=[]
    for i in range(1,len(candles)):
        for j in range(max(0,i-20),i):
            if abs(candles[i].high-candles[j].high)/max(candles[i].high,1e-9)<=tolerance: highs.append(candles[i].high)
            if abs(candles[i].low-candles[j].low)/max(candles[i].low,1e-9)<=tolerance: lows.append(candles[i].low)
    last=candles[-1]
    return {"equal_highs":sorted(set(highs))[-5:],"equal_lows":sorted(set(lows))[-5:],"buy_side_sweep":bool(highs and last.high>max(highs)),"sell_side_sweep":bool(lows and last.low<min(lows))}

def analyze_zones(candles: list[Candle]) -> dict:
    if len(candles)<20: raise ValueError("at least 20 candles required")
    fvg=detect_fvg(candles); obs=detect_order_blocks(candles); liq=detect_liquidity(candles)
    score=0.0; reasons=[]
    if fvg and fvg[-1].kind=="BULLISH_FVG": score+=0.5; reasons.append("recent bullish FVG")
    if fvg and fvg[-1].kind=="BEARISH_FVG": score-=0.5; reasons.append("recent bearish FVG")
    if obs and obs[-1].kind=="BULLISH_OB": score+=0.5; reasons.append("recent bullish order block")
    if obs and obs[-1].kind=="BEARISH_OB": score-=0.5; reasons.append("recent bearish order block")
    if liq["sell_side_sweep"]: score+=0.75; reasons.append("sell-side liquidity sweep")
    if liq["buy_side_sweep"]: score-=0.75; reasons.append("buy-side liquidity sweep")
    return {"score":score,"bias":"BULLISH" if score>0 else "BEARISH" if score<0 else "NEUTRAL","fvg":[asdict(x) for x in fvg[-20:]],"order_blocks":[asdict(x) for x in obs[-20:]],"liquidity":liq,"reasons":reasons}
