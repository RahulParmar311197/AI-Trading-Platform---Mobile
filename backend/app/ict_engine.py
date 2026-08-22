from __future__ import annotations
from dataclasses import asdict,dataclass
from app.market_data import Candle
@dataclass(frozen=True)
class Swing: index:int; price:float; kind:str
@dataclass(frozen=True)
class FairValueGap: index:int; direction:str; low:float; high:float
@dataclass(frozen=True)
class LiquidityPool: index:int; kind:str; price:float; tolerance:float
@dataclass(frozen=True)
class OrderBlock: index:int; direction:str; low:float; high:float; displacement:float

def swings(candles:list[Candle],lookback:int=2)->list[Swing]:
    if lookback<1:return []
    out=[]
    for i in range(lookback,len(candles)-lookback):
        c=candles[i]; around=candles[i-lookback:i]+candles[i+1:i+lookback+1]
        if all(c.high>x.high for x in around):out.append(Swing(i,c.high,'HIGH'))
        if all(c.low<x.low for x in around):out.append(Swing(i,c.low,'LOW'))
    return out

def fair_value_gaps(candles:list[Candle])->list[FairValueGap]:
    out=[]
    for i in range(2,len(candles)):
        a,c=candles[i-2],candles[i]
        if c.low>a.high:out.append(FairValueGap(i,'BULLISH',a.high,c.low))
        elif c.high<a.low:out.append(FairValueGap(i,'BEARISH',c.high,a.low))
    return out

def liquidity_pools(candles:list[Candle],lookback:int=30,tolerance_bps:float=5.0)->list[LiquidityPool]:
    sw=swings(candles); tol=max(1e-12,tolerance_bps/10000); pools=[]
    for i,x in enumerate(sw):
        for y in sw[:i]:
            if x.kind==y.kind and abs(x.price-y.price)/max(abs(x.price),1e-12)<=tol:
                pools.append(LiquidityPool(x.index,'EQUAL_HIGH' if x.kind=='HIGH' else 'EQUAL_LOW',(x.price+y.price)/2,tol));break
    return pools[-lookback:]

def liquidity_sweeps(candles:list[Candle],pools:list[LiquidityPool])->list[dict]:
    out=[]
    for p in pools:
        for i in range(p.index+1,len(candles)):
            c=candles[i]
            if p.kind=='EQUAL_HIGH' and c.high>p.price and c.close<p.price:out.append({'index':i,'direction':'BEARISH','price':p.price})
            elif p.kind=='EQUAL_LOW' and c.low<p.price and c.close>p.price:out.append({'index':i,'direction':'BULLISH','price':p.price})
    return out

def order_blocks(candles:list[Candle],displacement_mult:float=1.5)->list[OrderBlock]:
    if len(candles)<4:return []
    out=[]
    for i in range(1,len(candles)-1):
        prev=candles[i]; nxt=candles[i+1]; rng=max(prev.high-prev.low,1e-12); move=abs(nxt.close-nxt.open)
        if move < displacement_mult*rng:continue
        if nxt.close>nxt.open and prev.close<prev.open:out.append(OrderBlock(i,'BULLISH',prev.low,prev.high,move/rng))
        elif nxt.close<nxt.open and prev.close>prev.open:out.append(OrderBlock(i,'BEARISH',prev.low,prev.high,move/rng))
    return out

def structure(candles:list[Candle])->dict:
    sw=swings(candles); highs=[x for x in sw if x.kind=='HIGH']; lows=[x for x in sw if x.kind=='LOW']; labels=[]
    for seq in (highs,lows):
        for n,x in enumerate(seq):
            if n:labels.append({'index':x.index,'type':(('HH' if x.price>seq[n-1].price else 'LH') if x.kind=='HIGH' else ('HL' if x.price>seq[n-1].price else 'LL')),'price':x.price})
    labels.sort(key=lambda x:x['index']); bos=None;choch=None;bias=None
    if len(highs)>=2 and len(lows)>=2:
        hh=highs[-1].price>highs[-2].price;hl=lows[-1].price>lows[-2].price;lh=highs[-1].price<highs[-2].price;ll=lows[-1].price<lows[-2].price
        if hh and hl:bos=bias='BULLISH'
        elif lh and ll:bos=bias='BEARISH'
    pools=liquidity_pools(candles); sweeps=liquidity_sweeps(candles,pools); fvg=fair_value_gaps(candles); obs=order_blocks(candles)
    return {'bias':bias,'bos':bos,'choch':choch,'swings':[asdict(x) for x in sw],'structure_labels':labels,'fvg':[asdict(x) for x in fvg],'liquidity_pools':[asdict(x) for x in pools],'liquidity_sweeps':sweeps,'order_blocks':[asdict(x) for x in obs]}
