from __future__ import annotations
from dataclasses import asdict,dataclass
from app.market_data import Candle
@dataclass(frozen=True)
class Swing:
    index:int; price:float; kind:str
@dataclass(frozen=True)
class FairValueGap:
    index:int; direction:str; low:float; high:float

def swings(candles:list[Candle],lookback:int=2)->list[Swing]:
    if lookback<1:return []
    out=[]
    for i in range(lookback,len(candles)-lookback):
        c=candles[i]; left=candles[i-lookback:i]; right=candles[i+1:i+lookback+1]
        if all(c.high>x.high for x in left+right):out.append(Swing(i,c.high,'HIGH'))
        if all(c.low<x.low for x in left+right):out.append(Swing(i,c.low,'LOW'))
    return out

def fair_value_gaps(candles:list[Candle])->list[FairValueGap]:
    out=[]
    for i in range(2,len(candles)):
        a,c=candles[i-2],candles[i]
        if c.low>a.high:out.append(FairValueGap(i,'BULLISH',a.high,c.low))
        elif c.high<a.low:out.append(FairValueGap(i,'BEARISH',c.high,a.low))
    return out

def structure(candles:list[Candle])->dict:
    sw=swings(candles); highs=[x for x in sw if x.kind=='HIGH']; lows=[x for x in sw if x.kind=='LOW']
    labels=[]
    for seq in (highs,lows):
        for n,x in enumerate(seq):
            if n==0:continue
            if x.kind=='HIGH': labels.append({'index':x.index,'type':'HH' if x.price>seq[n-1].price else 'LH','price':x.price})
            else: labels.append({'index':x.index,'type':'HL' if x.price>seq[n-1].price else 'LL','price':x.price})
    labels.sort(key=lambda x:x['index'])
    bos=None;choch=None;bias=None
    if len(highs)>=2 and len(lows)>=2:
        hh=highs[-1].price>highs[-2].price; hl=lows[-1].price>lows[-2].price
        lh=highs[-1].price<highs[-2].price; ll=lows[-1].price<lows[-2].price
        if hh and hl:bos=bias='BULLISH'
        elif lh and ll:bos=bias='BEARISH'
        prior='BULLISH' if len(labels)>=3 and labels[-3]['type'] in ('HH','HL') else 'BEARISH' if labels else None
        if bos and prior and bos!=prior:choch=bos
    return {'bias':bias,'bos':bos,'choch':choch,'swings':[asdict(x) for x in sw],'structure_labels':labels,'fvg':[asdict(x) for x in fair_value_gaps(candles)]}
