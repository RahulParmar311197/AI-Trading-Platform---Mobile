from __future__ import annotations
from dataclasses import dataclass
from app.smc_structure import StructureSignal, StructureEvent
from app.ict_liquidity import LiquiditySweep
from app.ict_fvg import FairValueGap
from app.ict_order_block import OrderBlock

@dataclass(frozen=True)
class ConfluenceConfig:
    min_score:int=60
    structure_weight:int=25
    liquidity_weight:int=20
    displacement_weight:int=15
    fvg_weight:int=15
    order_block_weight:int=15
    rr_weight:int=10

@dataclass(frozen=True)
class SMCICTSetup:
    action:str
    score:int
    confidence:float
    reasons:tuple[str,...]
    entry_zone_low:float|None
    entry_zone_high:float|None
    stop_reference:float|None


def score_setup(*,structure:StructureSignal|None,sweep:LiquiditySweep|None,fvg:FairValueGap|None,order_block:OrderBlock|None,rr:float=0.0,config:ConfluenceConfig|None=None)->SMCICTSetup:
    cfg=config or ConfluenceConfig(); score=0; reasons=[]; action='NONE'; lows=[]; highs=[]; stop=None
    if structure:
        action='BUY' if structure.direction=='BULLISH' else 'SELL'; score+=cfg.structure_weight; reasons.append(structure.event.value)
    if sweep:
        expected='SELL_SIDE_SWEEP' if action=='BUY' else 'BUY_SIDE_SWEEP'
        if sweep.kind==expected: score+=cfg.liquidity_weight; reasons.append('LIQUIDITY_SWEEP')
        if sweep.displacement: score+=cfg.displacement_weight; reasons.append('DISPLACEMENT')
    if fvg and action!='NONE':
        if (action=='BUY' and fvg.kind=='BULLISH') or (action=='SELL' and fvg.kind=='BEARISH'):
            score+=cfg.fvg_weight; reasons.append('FVG'); lows.append(fvg.lower); highs.append(fvg.upper)
    if order_block and action!='NONE':
        if (action=='BUY' and order_block.kind=='BULLISH') or (action=='SELL' and order_block.kind=='BEARISH'):
            score+=cfg.order_block_weight; reasons.append('ORDER_BLOCK'); lows.append(order_block.lower); highs.append(order_block.upper)
    if rr>=2.0: score+=cfg.rr_weight; reasons.append('RR>=2')
    confidence=min(100.0,float(score));
    if score<cfg.min_score: action='NONE'
    if lows and highs: zone_low=min(lows); zone_high=max(highs)
    else: zone_low=zone_high=None
    return SMCICTSetup(action,score,confidence,tuple(reasons),zone_low,zone_high,stop)
