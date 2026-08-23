from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from app.market_data import Candle

@dataclass(frozen=True)
class TechnicalSnapshot:
    ema_fast:float|None; ema_slow:float|None; rsi:float|None; macd:float|None; atr:float|None; adx:float|None; vwap:float|None; bollinger_upper:float|None; bollinger_lower:float|None; trend:str

class TechnicalAnalysisEngine:
    def _closes(self,c): return [x.close for x in c]
    def ema(self,values:list[float],period:int)->float|None:
        if period<1: raise ValueError('period must be positive')
        if len(values)<period:return None
        e=sum(values[:period])/period; a=2/(period+1)
        for v in values[period:]: e=(v-e)*a+e
        return e
    def rsi(self,values:list[float],period:int=14)->float|None:
        if len(values)<period+1:return None
        gains=[max(values[i]-values[i-1],0) for i in range(1,len(values))]; losses=[max(values[i-1]-values[i],0) for i in range(1,len(values))]
        ag=sum(gains[:period])/period; al=sum(losses[:period])/period
        for g,l in zip(gains[period:],losses[period:]): ag=(ag*(period-1)+g)/period; al=(al*(period-1)+l)/period
        return 100.0 if al==0 else 100-(100/(1+ag/al))
    def atr(self,candles:list[Candle],period:int=14)->float|None:
        if len(candles)<period+1:return None
        tr=[]
        for i in range(1,len(candles)):
            c,p=candles[i],candles[i-1]; tr.append(max(c.high-c.low,abs(c.high-p.close),abs(c.low-p.close)))
        return sum(tr[-period:])/period
    def vwap(self,candles:list[Candle])->float|None:
        if not candles:return None
        tv=sum(((c.high+c.low+c.close)/3)*c.volume for c in candles); vol=sum(c.volume for c in candles); return tv/vol if vol else None
    def bollinger(self,values:list[float],period:int=20,k:float=2)->tuple[float|None,float|None]:
        if len(values)<period:return None,None
        w=values[-period:]; m=sum(w)/period; sd=sqrt(sum((x-m)**2 for x in w)/period); return m+k*sd,m-k*sd
    def snapshot(self,candles:list[Candle])->TechnicalSnapshot:
        v=self._closes(candles); fast=self.ema(v,12); slow=self.ema(v,26); upper,lower=self.bollinger(v); macd=fast-slow if fast is not None and slow is not None else None; r=self.rsi(v); a=self.atr(candles); vw=self.vwap(candles); trend='BULLISH' if fast is not None and slow is not None and fast>slow else 'BEARISH' if fast is not None and slow is not None else 'NEUTRAL'
        return TechnicalSnapshot(fast,slow,r,macd,a,None,vw,upper,lower,trend)
