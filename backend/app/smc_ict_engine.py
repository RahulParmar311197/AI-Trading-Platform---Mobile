from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class Swing:
    index:int; price:float; kind:str

@dataclass(frozen=True)
class StructureEvent:
    index:int; kind:str; level:float

@dataclass(frozen=True)
class FairValueGap:
    index:int; direction:str; low:float; high:float

@dataclass(frozen=True)
class OrderBlock:
    index:int; direction:str; low:float; high:float

class SMCICTEngine:
    def swings(self,candles:list[Candle],lookback:int=2)->list[Swing]:
        if lookback<1: raise ValueError('lookback must be positive')
        out=[]
        for i in range(lookback,len(candles)-lookback):
            c=candles[i]; left=candles[i-lookback:i]; right=candles[i+1:i+1+lookback]
            if c.high>max(x.high for x in left+right): out.append(Swing(i,c.high,'HIGH'))
            if c.low<min(x.low for x in left+right): out.append(Swing(i,c.low,'LOW'))
        return out

    def structure(self,candles:list[Candle],lookback:int=2)->list[StructureEvent]:
        swings=self.swings(candles,lookback); highs=[s for s in swings if s.kind=='HIGH']; lows=[s for s in swings if s.kind=='LOW']; events=[]
        for i,c in enumerate(candles):
            if highs and c.close>highs[-1].price and i>highs[-1].index: events.append(StructureEvent(i,'BOS_BULLISH',highs[-1].price))
            if lows and c.close<lows[-1].price and i>lows[-1].index: events.append(StructureEvent(i,'BOS_BEARISH',lows[-1].price))
        return events

    def fair_value_gaps(self,candles:list[Candle])->list[FairValueGap]:
        out=[]
        for i in range(2,len(candles)):
            a,b,c=candles[i-2:i+1]
            if a.high<c.low: out.append(FairValueGap(i,'BULLISH',a.high,c.low))
            if a.low>c.high: out.append(FairValueGap(i,'BEARISH',c.high,a.low))
        return out

    def order_blocks(self,candles:list[Candle])->list[OrderBlock]:
        out=[]
        for i in range(1,len(candles)):
            prev,c=candles[i-1],candles[i]
            if c.close>c.open and prev.close<prev.open and c.close>prev.high: out.append(OrderBlock(i,'BULLISH',prev.low,prev.high))
            if c.close<c.open and prev.close>prev.open and c.close<prev.low: out.append(OrderBlock(i,'BEARISH',prev.low,prev.high))
        return out

    def analyze(self,candles:list[Candle])->dict:
        swings=self.swings(candles); structure=self.structure(candles); gaps=self.fair_value_gaps(candles); blocks=self.order_blocks(candles)
        bull=sum(x.kind=='BOS_BULLISH' for x in structure)+sum(x.direction=='BULLISH' for x in gaps)+sum(x.direction=='BULLISH' for x in blocks)
        bear=sum(x.kind=='BOS_BEARISH' for x in structure)+sum(x.direction=='BEARISH' for x in gaps)+sum(x.direction=='BEARISH' for x in blocks)
        return {'bias':'BULLISH' if bull>bear else 'BEARISH' if bear>bull else 'NEUTRAL','score':bull-bear,'swings':swings,'structure':structure,'fair_value_gaps':gaps,'order_blocks':blocks}
