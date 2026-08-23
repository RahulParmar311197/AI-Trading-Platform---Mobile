from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle

@dataclass(frozen=True)
class OrderBlock:
    index:int
    kind:str  # BULLISH / BEARISH
    lower:float
    upper:float
    origin_index:int
    mitigated:bool=False

@dataclass(frozen=True)
class OrderBlockState:
    block:OrderBlock
    mitigated:bool
    mitigation_index:int|None


def detect_order_blocks(candles:list[Candle], displacement_threshold:float=0.002)->list[OrderBlock]:
    if displacement_threshold<0: raise ValueError('displacement_threshold must be non-negative')
    out=[]
    for i in range(1,len(candles)):
        prev,c=candles[i-1],candles[i]
        bullish_move=(c.close>c.open and c.close>prev.high and (c.close-c.open)/max(abs(prev.close),1e-12)>=displacement_threshold)
        bearish_move=(c.close<c.open and c.close<prev.low and (c.open-c.close)/max(abs(prev.close),1e-12)>=displacement_threshold)
        if bullish_move and prev.close<prev.open:
            out.append(OrderBlock(i,'BULLISH',prev.low,prev.high,i-1))
        if bearish_move and prev.close>prev.open:
            out.append(OrderBlock(i,'BEARISH',prev.low,prev.high,i-1))
    return out


def order_block_state(candles:list[Candle], block:OrderBlock)->OrderBlockState:
    for i,c in enumerate(candles[block.index+1:],block.index+1):
        if block.kind=='BULLISH' and c.low<=block.lower: return OrderBlockState(block,True,i)
        if block.kind=='BEARISH' and c.high>=block.upper: return OrderBlockState(block,True,i)
    return OrderBlockState(block,False,None)
