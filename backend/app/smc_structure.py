from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.market_data import Candle

class StructureEvent(str, Enum):
    NONE='NONE'; BOS='BOS'; CHOCH='CHOCH'

@dataclass(frozen=True)
class SwingPoint:
    index:int
    price:float
    kind:str  # HIGH / LOW

@dataclass(frozen=True)
class StructureSignal:
    index:int
    event:StructureEvent
    direction:str  # BULLISH / BEARISH
    broken_level:float
    swing_index:int


def detect_swings(candles:list[Candle], left:int=2, right:int=2)->list[SwingPoint]:
    if left<1 or right<1: raise ValueError('left/right must be positive')
    out=[]
    for i in range(left,len(candles)-right):
        c=candles[i]; highs=[candles[j].high for j in range(i-left,i+right+1)]; lows=[candles[j].low for j in range(i-left,i+right+1)]
        if c.high==max(highs) and highs.count(c.high)==1: out.append(SwingPoint(i,c.high,'HIGH'))
        if c.low==min(lows) and lows.count(c.low)==1: out.append(SwingPoint(i,c.low,'LOW'))
    return out


def detect_structure(candles:list[Candle], swings:list[SwingPoint]|None=None)->list[StructureSignal]:
    if not candles: return []
    swings=swings if swings is not None else detect_swings(candles)
    highs=[s for s in swings if s.kind=='HIGH']; lows=[s for s in swings if s.kind=='LOW']; out=[]
    last_high=None; last_low=None; trend=None; broken_high=set(); broken_low=set()
    for i,c in enumerate(candles):
        for s in highs:
            if s.index < i: last_high=s
        for s in lows:
            if s.index < i: last_low=s
        if last_high and c.close>last_high.price and last_high.index not in broken_high:
            event=StructureEvent.CHOCH if trend=='BEARISH' else StructureEvent.BOS
            out.append(StructureSignal(i,event,'BULLISH',last_high.price,last_high.index)); broken_high.add(last_high.index); trend='BULLISH'
        if last_low and c.close<last_low.price and last_low.index not in broken_low:
            event=StructureEvent.CHOCH if trend=='BULLISH' else StructureEvent.BOS
            out.append(StructureSignal(i,event,'BEARISH',last_low.price,last_low.index)); broken_low.add(last_low.index); trend='BEARISH'
    return out
