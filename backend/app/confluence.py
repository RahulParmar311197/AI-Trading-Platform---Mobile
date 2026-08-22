from __future__ import annotations
from app.ict_engine import structure
from app.indicators import atr,ema
from app.market_data import Candle

def score(candles:list[Candle])->dict:
    if not candles:return {'score':0,'bias':'NEUTRAL','reasons':[]}
    closes=[c.close for c in candles]; highs=[c.high for c in candles]; lows=[c.low for c in candles]; ict=structure(candles)
    fast=ema(closes,min(20,len(closes))); a=atr(highs,lows,closes,min(14,len(closes))); last=closes[-1]; points=0; reasons=[]
    if ict['bos']=='BULLISH':points+=2;reasons.append('bullish BOS')
    elif ict['bos']=='BEARISH':points-=2;reasons.append('bearish BOS')
    if ict['choch']=='BULLISH':points+=2;reasons.append('bullish CHoCH')
    elif ict['choch']=='BEARISH':points-=2;reasons.append('bearish CHoCH')
    if ict['liquidity_sweeps']:
        sweep=ict['liquidity_sweeps'][-1]
        if sweep['direction']=='BULLISH':points+=2;reasons.append('bullish liquidity sweep')
        elif sweep['direction']=='BEARISH':points-=2;reasons.append('bearish liquidity sweep')
    if ict['fvg']:
        fvg=ict['fvg'][-1]
        if fvg['direction']=='BULLISH' and last>=fvg['low']:points+=1;reasons.append('bullish FVG')
        elif fvg['direction']=='BEARISH' and last<=fvg['high']:points-=1;reasons.append('bearish FVG')
    if fast is not None and last>fast:points+=1;reasons.append('price above EMA')
    elif fast is not None and last<fast:points-=1;reasons.append('price below EMA')
    bias='BULLISH' if points>=2 else 'BEARISH' if points<=-2 else 'NEUTRAL'
    return {'score':max(-9,min(9,points)),'bias':bias,'reasons':reasons,'atr':a,'ict':ict}
