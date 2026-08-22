from __future__ import annotations
from dataclasses import dataclass
from app.confluence import score
from app.market_data import Candle
from app.mtf_engine import confirm
@dataclass(frozen=True)
class TradeSignal:
    action:str; entry:float; stop_loss:float; target:float; risk_reward:float; confidence:float; reason:list[str]

def generate_signal(candles:list[Candle],min_score:int=2,htf_candles:list[Candle]|None=None,require_mtf:bool=False)->TradeSignal|None:
    if len(candles)<20:return None
    result=score(candles); reasons=list(result.get('reasons',[])); mtf_score=0
    if htf_candles is not None:
        mtf=confirm(htf_candles,candles)
        reasons.append(f"MTF: {mtf.htf_bias} HTF / {mtf.ltf_bias} LTF")
        if require_mtf and not mtf.aligned:return None
        if mtf.aligned:
            mtf_score=mtf.score if mtf.htf_bias==result['bias'] else -mtf.score
            reasons.append('HTF/LTF structure aligned')
        elif mtf.htf_bias in ('BULLISH','BEARISH') and mtf.htf_bias!=result['bias']:
            return None if require_mtf else TradeSignal('NO_TRADE',candles[-1].close, candles[-1].close, candles[-1].close,0,0,reasons+['HTF/LTF conflict'])
    total=result['score']+mtf_score
    if abs(total)<min_score:return None
    last=candles[-1].close; a=result.get('atr') or (candles[-1].high-candles[-1].low)
    if not a:return None
    if result['bias']=='BULLISH':entry,stop,target,action=last,last-1.5*a,last+3*a,'BUY'
    elif result['bias']=='BEARISH':entry,stop,target,action=last,last+1.5*a,last-3*a,'SELL'
    else:return None
    risk=abs(entry-stop); reward=abs(target-entry); confidence=min(.99,.5+abs(total)*.07)
    return TradeSignal(action,entry,stop,target,reward/risk if risk else 0,confidence,reasons)
