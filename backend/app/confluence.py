from __future__ import annotations
from app.ict_engine import structure
from app.indicators import atr,ema
from app.market_data import Candle

def score(candles:list[Candle])->dict:
    if not candles:return {'score':0,'bias':'NEUTRAL','reasons':[]}
    closes=[c.close for c in candles]; highs=[c.high for c in candles]; lows=[c.low for c in candles]; ict=structure(candles); fast=ema(closes,min(20,len(closes))); a=atr(highs,lows,closes,min(14,len(closes))); last=closes[-1]; points=0; reasons=[]
    # BOS and CHoCH describe the same structural state transition family.
    # Count only one structural signal so a single event cannot receive +4/-4.
    if ict['choch']=='BULLISH':points+=2;reasons.append('bullish CHoCH')
    elif ict['choch']=='BEARISH':points-=2;reasons.append('bearish CHoCH')
    elif ict['bos']=='BULLISH':points+=2;reasons.append('bullish BOS')
    elif ict['bos']=='BEARISH':points-=2;reasons.append('bearish BOS')
    if ict['liquidity_sweeps']:
        s=ict['liquidity_sweeps'][-1]; points+=2 if s['direction']=='BULLISH' else -2; reasons.append(s['direction'].lower()+' liquidity sweep')
    if ict['fvg']:
        f=ict['fvg'][-1]
        if f['direction']=='BULLISH' and last>=f['low']:points+=1;reasons.append('bullish FVG')
        elif f['direction']=='BEARISH' and last<=f['high']:points-=1;reasons.append('bearish FVG')
    if ict.get('order_blocks'):
        ob=ict['order_blocks'][-1]
        if ob['direction']=='BULLISH' and ob['low']<=last<=ob['high']:points+=2;reasons.append('bullish order block')
        elif ob['direction']=='BEARISH' and ob['low']<=last<=ob['high']:points-=2;reasons.append('bearish order block')
    dr=ict.get('dealing_range',{}); loc=dr.get('location')
    if loc=='DISCOUNT':points+=1;reasons.append('price in discount')
    elif loc=='PREMIUM':points-=1;reasons.append('price in premium')
    if fast is not None and last>fast:points+=1;reasons.append('price above EMA')
    elif fast is not None and last<fast:points-=1;reasons.append('price below EMA')
    bias='BULLISH' if points>=3 else 'BEARISH' if points<=-3 else 'NEUTRAL'
    return {'score':max(-12,min(12,points)),'bias':bias,'reasons':reasons,'atr':a,'ict':ict}
