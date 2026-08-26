from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.confluence import score
from app.market_data import Candle, validate_freshness
from app.mtf_engine import confirm

@dataclass(frozen=True)
class TradeSignal:
    action:str; entry:float; stop_loss:float; target:float; risk_reward:float; confidence:float; reason:list[str]

def generate_signal(candles:list[Candle],min_score:int=2,htf_candles:list[Candle]|None=None,require_mtf:bool=False,max_age_seconds:float|None=None,now:datetime|None=None)->TradeSignal|None:
    if len(candles)<20:return None
    if max_age_seconds is not None and not validate_freshness(candles[-1].timestamp,max_age_seconds=max_age_seconds,now=now).fresh:return None
    if htf_candles is not None and max_age_seconds is not None and not validate_freshness(htf_candles[-1].timestamp,max_age_seconds=max_age_seconds,now=now).fresh:return None
    result=score(candles); reasons=list(result.get('reasons',[])); mtf_score=0
    if htf_candles is not None:
        mtf=confirm(htf_candles,candles); reasons.append(f"MTF: {mtf.htf_bias} HTF / {mtf.ltf_bias} LTF")
        if not mtf.aligned:
            if require_mtf:return None
            if mtf.htf_bias in ('BULLISH','BEARISH') and mtf.htf_bias!=result['bias']:return None
        else:
            mtf_score=mtf.score if mtf.htf_bias==result['bias'] else -mtf.score; reasons.append('HTF/LTF structure aligned')
    total=result['score']+mtf_score
    if abs(total)<min_score:return None
    last=candles[-1].close; a=result.get('atr') or (candles[-1].high-candles[-1].low)
    if not a:return None
    if result['bias']=='BULLISH':entry,stop,target,action=last,last-1.5*a,last+3*a,'BUY'
    elif result['bias']=='BEARISH':entry,stop,target,action=last,last+1.5*a,last-3*a,'SELL'
    else:return None
    risk=abs(entry-stop); reward=abs(target-entry); confidence=min(.99,.5+abs(total)*.07)
    return TradeSignal(action,entry,stop,target,reward/risk if risk else 0,confidence,reasons)
