from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from app.market_data import Candle

@dataclass(frozen=True)
class TechnicalConfirmation:
    adx:float|None; momentum:float|None; support:float|None; resistance:float|None; volume_ratio:float|None; score:float; bias:str

class TechnicalConfirmationEngine:
    def adx(self,candles:list[Candle],period:int=14)->float|None:
        if len(candles)<period+1:return None
        trs=[]; plus=[]; minus=[]
        for i in range(1,len(candles)):
            c,p=candles[i],candles[i-1]; trs.append(max(c.high-c.low,abs(c.high-p.close),abs(c.low-p.close)))
            up=c.high-p.high; dn=p.low-c.low; plus.append(up if up>dn and up>0 else 0); minus.append(dn if dn>up and dn>0 else 0)
        tr=sum(trs[-period:]); p=sum(plus[-period:]); m=sum(minus[-period:])
        if tr==0:return 0.0
        pdi=100*p/tr; mdi=100*m/tr; return 100*abs(pdi-mdi)/(pdi+mdi) if pdi+mdi else 0.0
    def analyze(self,candles:list[Candle],lookback:int=20)->TechnicalConfirmation:
        if not candles:return TechnicalConfirmation(None,None,None,None,None,0.0,'NEUTRAL')
        w=candles[-lookback:]; support=min(c.low for c in w); resistance=max(c.high for c in w); momentum=(candles[-1].close-candles[max(0,len(candles)-min(lookback,len(candles)))].close)
        avg=sum(c.volume for c in w)/len(w); vr=candles[-1].volume/avg if avg else None; adx=self.adx(candles); score=0.0
        if momentum>0:score+=1
        elif momentum<0:score-=1
        if candles[-1].close>resistance:score+=1
        if candles[-1].close<support:score-=1
        if vr is not None and vr>1.2:score+=0.5 if momentum>0 else -0.5 if momentum<0 else 0
        if adx is not None and adx>=20:score+=0.5 if momentum>0 else -0.5 if momentum<0 else 0
        return TechnicalConfirmation(adx,momentum,support,resistance,vr,score,'BULLISH' if score>0 else 'BEARISH' if score<0 else 'NEUTRAL')
