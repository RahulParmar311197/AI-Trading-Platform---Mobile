from __future__ import annotations
from dataclasses import dataclass
from app.market_data import Candle
from app.smc_confluence import SMCConfluenceEngine
from app.technical_analysis import TechnicalAnalysisEngine
from app.technical_confirmation import TechnicalConfirmationEngine

@dataclass(frozen=True)
class SignalWeights:
    smc:float=0.55
    technical:float=0.35
    trend:float=0.10
    threshold:float=0.25

class UnifiedSignalEngine:
    def __init__(self,weights:SignalWeights|None=None): self.weights=weights or SignalWeights()
    def analyze(self,candles:list[Candle])->dict:
        if not candles:return {'direction':'NEUTRAL','confidence':0.0,'score':0.0,'tradeable':False,'reasons':['NO_MARKET_DATA']}
        smc=SMCConfluenceEngine().analyze(candles); ta=TechnicalAnalysisEngine().snapshot(candles); tc=TechnicalConfirmationEngine().analyze(candles)
        smc_score=max(-1,min(1,smc['score']/10)); ta_score=1 if ta.trend=='BULLISH' else -1 if ta.trend=='BEARISH' else 0; conf_score=max(-1,min(1,tc.score/3))
        score=smc_score*self.weights.smc+conf_score*self.weights.technical+ta_score*self.weights.trend; direction='BULLISH' if score>=self.weights.threshold else 'BEARISH' if score<=-self.weights.threshold else 'NEUTRAL'; confidence=min(1,abs(score)); reasons=[f'SMC={smc_score:.2f}',f'TA={conf_score:.2f}',f'TREND={ta_score:.2f}']; tradeable=direction!='NEUTRAL' and confidence>=self.weights.threshold
        return {'direction':direction,'confidence':confidence,'score':score,'tradeable':tradeable,'reasons':reasons,'smc':smc,'technical':ta,'confirmation':tc}
