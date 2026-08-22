from __future__ import annotations
from dataclasses import dataclass
from app.unified_signal import UnifiedSignalEngine
from app.market_data import Candle

@dataclass(frozen=True)
class AIDecision:
    action:str
    confidence:float
    score:float
    tradeable:bool
    reasons:tuple[str,...]

class AIDecisionEngine:
    def __init__(self,min_confidence:float=0.60):
        if not 0<=min_confidence<=1: raise ValueError('min_confidence must be between 0 and 1')
        self.min_confidence=min_confidence

    def decide(self,candles:list[Candle])->AIDecision:
        signal=UnifiedSignalEngine().analyze(candles)
        reasons=list(signal['reasons'])
        if signal['direction']=='NEUTRAL':
            reasons.append('NO_DIRECTIONAL_EDGE'); return AIDecision('WAIT',signal['confidence'],signal['score'],False,tuple(reasons))
        if signal['confidence']<self.min_confidence:
            reasons.append('CONFIDENCE_BELOW_THRESHOLD'); return AIDecision('WAIT',signal['confidence'],signal['score'],False,tuple(reasons))
        if not signal['tradeable']:
            reasons.append('SIGNAL_NOT_TRADEABLE'); return AIDecision('WAIT',signal['confidence'],signal['score'],False,tuple(reasons))
        action='BUY' if signal['direction']=='BULLISH' else 'SELL'
        return AIDecision(action,signal['confidence'],signal['score'],True,tuple(reasons))
