from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle
from app.smc_structure import SwingPoint

@dataclass(frozen=True)
class LiquidityPool:
    kind:str  # BUY_SIDE / SELL_SIDE
    price:float
    first_index:int
    second_index:int
    tolerance:float

@dataclass(frozen=True)
class LiquiditySweep:
    index:int
    kind:str  # BUY_SIDE_SWEEP / SELL_SIDE_SWEEP
    liquidity_price:float
    close_price:float
    displacement:bool


def detect_equal_liquidity(swings:list[SwingPoint], tolerance:float=0.001)->list[LiquidityPool]:
    if tolerance<0: raise ValueError('tolerance must be non-negative')
    pools=[]
    for i,a in enumerate(swings):
        for b in swings[i+1:]:
            if a.kind!=b.kind: continue
            base=max(abs(a.price),abs(b.price),1.0)
            if abs(a.price-b.price)/base<=tolerance:
                kind='BUY_SIDE' if a.kind=='HIGH' else 'SELL_SIDE'
                pools.append(LiquidityPool(kind,(a.price+b.price)/2,a.index,b.index,tolerance)); break
    return pools


def detect_liquidity_sweeps(candles:list[Candle], pools:list[LiquidityPool], displacement_threshold:float=0.001)->list[LiquiditySweep]:
    if displacement_threshold<0: raise ValueError('displacement_threshold must be non-negative')
    out=[]
    for i,c in enumerate(candles):
        for p in pools:
            if i<=p.second_index: continue
            if p.kind=='BUY_SIDE' and c.high>p.price and c.close<p.price:
                displaced=(c.open-c.close)/max(c.open,1e-12)>=displacement_threshold
                out.append(LiquiditySweep(i,'BUY_SIDE_SWEEP',p.price,c.close,displaced))
            elif p.kind=='SELL_SIDE' and c.low<p.price and c.close>p.price:
                displaced=(c.close-c.open)/max(c.open,1e-12)>=displacement_threshold
                out.append(LiquiditySweep(i,'SELL_SIDE_SWEEP',p.price,c.close,displaced))
    return out
