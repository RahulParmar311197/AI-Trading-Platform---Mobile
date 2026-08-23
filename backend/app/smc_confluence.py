from __future__ import annotations
from dataclasses import dataclass
from app.smc_ict_engine import SMCICTEngine
from app.liquidity_engine import LiquidityEngine
from app.market_data import Candle

@dataclass(frozen=True)
class ConfluenceWeights:
    structure:float=3.0
    fvg:float=2.0
    order_block:float=2.0
    liquidity_sweep:float=2.0
    zone:float=1.0
    threshold:float=5.0

class SMCConfluenceEngine:
    def __init__(self,weights:ConfluenceWeights|None=None): self.weights=weights or ConfluenceWeights()
    def analyze(self,candles:list[Candle])->dict:
        if not candles:return {'bias':'NEUTRAL','score':0.0,'confidence':0.0,'components':{}}
        smc=SMCICTEngine().analyze(candles); liq=LiquidityEngine().analyze(candles); bull=bear=0.0; components={}
        structure=sum(1 if x.kind=='BOS_BULLISH' else -1 for x in smc['structure']); fvg=sum(1 if x.direction=='BULLISH' else -1 for x in smc['fair_value_gaps']); ob=sum(1 if x.direction=='BULLISH' else -1 for x in smc['order_blocks']); sweep=sum(1 if x.direction=='BULLISH' else -1 for x in liq['sweeps']); zone=1 if liq['zone']=='DISCOUNT' else -1 if liq['zone']=='PREMIUM' else 0
        for name,value,weight in [('structure',structure,self.weights.structure),('fvg',fvg,self.weights.fvg),('order_block',ob,self.weights.order_block),('liquidity_sweep',sweep,self.weights.liquidity_sweep),('zone',zone,self.weights.zone)]: components[name]=value*weight
        score=sum(components.values()); confidence=min(1.0,abs(score)/sum((self.weights.structure,self.weights.fvg,self.weights.order_block,self.weights.liquidity_sweep,self.weights.zone))); bias='BULLISH' if score>=self.weights.threshold else 'BEARISH' if score<=-self.weights.threshold else 'NEUTRAL'; return {'bias':bias,'score':score,'confidence':confidence,'components':components,'structure':smc,'liquidity':liq}
