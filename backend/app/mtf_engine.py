from __future__ import annotations
from dataclasses import dataclass
from app.ict_engine import structure
from app.market_data import Candle
@dataclass(frozen=True)
class MTFResult:
    htf_bias:str
    ltf_bias:str
    aligned:bool
    score:int

def confirm(htf_candles:list[Candle],ltf_candles:list[Candle])->MTFResult:
    if not htf_candles or not ltf_candles: return MTFResult('UNKNOWN','UNKNOWN',False,0)
    h=structure(htf_candles); l=structure(ltf_candles); hb=h.get('bias') or 'NEUTRAL'; lb=l.get('bias') or 'NEUTRAL'
    aligned=hb in ('BULLISH','BEARISH') and hb==lb
    return MTFResult(hb,lb,aligned,2 if aligned else 0)

def confirm_dict(htf_candles:list[Candle],ltf_candles:list[Candle])->dict:
    r=confirm(htf_candles,ltf_candles)
    return {'htf_bias':r.htf_bias,'ltf_bias':r.ltf_bias,'aligned':r.aligned,'score':r.score}
