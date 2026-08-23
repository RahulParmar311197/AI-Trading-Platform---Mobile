from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class LiquidityLevel:
    price:float; kind:str; index:int

@dataclass(frozen=True)
class LiquiditySweep:
    index:int; direction:str; level:float

@dataclass(frozen=True)
class DealingRange:
    high:float; low:float; equilibrium:float

class LiquidityEngine:
    def equal_levels(self,candles:list[Candle],tolerance:float=0.001)->list[LiquidityLevel]:
        if tolerance<0: raise ValueError('tolerance must be non-negative')
        levels=[]
        for i in range(1,len(candles)-1):
            c=candles[i]
            if abs(c.high-candles[i-1].high)<=max(c.high*tolerance,1e-9): levels.append(LiquidityLevel(c.high,'BUY_SIDE',i))
            if abs(c.low-candles[i-1].low)<=max(c.low*tolerance,1e-9): levels.append(LiquidityLevel(c.low,'SELL_SIDE',i))
        return levels

    def sweeps(self,candles:list[Candle],lookback:int=10)->list[LiquiditySweep]:
        if lookback<1: raise ValueError('lookback must be positive')
        out=[]
        for i in range(lookback,len(candles)):
            window=candles[i-lookback:i]; high=max(x.high for x in window); low=min(x.low for x in window); c=candles[i]
            if c.high>high and c.close<high: out.append(LiquiditySweep(i,'BEARISH',high))
            if c.low<low and c.close>low: out.append(LiquiditySweep(i,'BULLISH',low))
        return out

    def dealing_range(self,candles:list[Candle])->DealingRange|None:
        if not candles:return None
        high=max(c.high for c in candles); low=min(c.low for c in candles)
        return DealingRange(high,low,(high+low)/2)

    def zone(self,price:float,dr:DealingRange)->str:
        if price>dr.equilibrium:return 'PREMIUM'
        if price<dr.equilibrium:return 'DISCOUNT'
        return 'EQUILIBRIUM'

    def analyze(self,candles:list[Candle])->dict:
        dr=self.dealing_range(candles); sweeps=self.sweeps(candles) if candles else []; levels=self.equal_levels(candles) if candles else []
        return {'dealing_range':dr,'zone':self.zone(candles[-1].close,dr) if dr else None,'liquidity_levels':levels,'sweeps':sweeps}
