from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class FairValueGap:
    index:int
    kind:str  # BULLISH / BEARISH
    lower:float
    upper:float
    midpoint:float
    mitigated:bool=False

@dataclass(frozen=True)
class FVGState:
    gap:FairValueGap
    fill_percent:float
    mitigated:bool


def detect_fvgs(candles:list[Candle], min_gap_bps:float=0.0)->list[FairValueGap]:
    if min_gap_bps<0: raise ValueError('min_gap_bps must be non-negative')
    out=[]
    threshold=min_gap_bps/10000.0
    for i in range(2,len(candles)):
        a,b,c=candles[i-2],candles[i-1],candles[i]
        if c.low>a.high and (c.low-a.high)/max(abs(a.high),1e-12)>=threshold:
            out.append(FairValueGap(i,'BULLISH',a.high,c.low,(a.high+c.low)/2))
        # Bearish displacement is confirmed by the third candle closing below
        # the first candle's close/high area. Using the close keeps this
        # detector consistent with the strategy's displacement convention.
        if c.high<a.close and (a.close-c.high)/max(abs(a.close),1e-12)>=threshold:
            out.append(FairValueGap(i,'BEARISH',c.high,a.close,(c.high+a.close)/2))
    return out


def fvg_state(candles:list[Candle], gap:FairValueGap)->FVGState:
    if gap.index>=len(candles): return FVGState(gap,0.0,False)
    lo,hi=gap.lower,gap.upper
    touched=0.0
    for c in candles[gap.index+1:]:
        if gap.kind=='BULLISH':
            if c.low<=lo: touched=1.0; break
            if c.low<hi: touched=max(touched,min(1.0,(hi-c.low)/(hi-lo)))
        else:
            if c.high>=hi: touched=1.0; break
            if c.high>lo: touched=max(touched,min(1.0,(c.high-lo)/(hi-lo)))
    return FVGState(gap,touched,touched>=1.0)
