from __future__ import annotations
from app.market_data import Candle
from app.smc_structure import detect_swings, detect_structure
from app.ict_liquidity import detect_equal_liquidity, detect_liquidity_sweeps
from app.ict_fvg import detect_fvgs
from app.ict_order_block import detect_order_blocks
from app.smc_ict_confluence import score_setup, ConfluenceConfig


def generate_smc_ict_signal(candles:list[Candle], min_score:int=60, config:ConfluenceConfig|None=None):
    if len(candles)<10: return None
    swings=detect_swings(candles)
    structures=detect_structure(candles,swings)
    pools=detect_equal_liquidity(swings)
    sweeps=detect_liquidity_sweeps(candles,pools)
    fvgs=detect_fvgs(candles)
    blocks=detect_order_blocks(candles)
    structure=next((x for x in reversed(structures) if x.index < len(candles)),None)
    sweep=next((x for x in reversed(sweeps) if x.index < len(candles)),None)
    fvg=next((x for x in reversed(fvgs) if not x.mitigated),None)
    block=next((x for x in reversed(blocks) if not x.mitigated),None)
    if structure is None: return None
    last=candles[-1].close
    if structure.direction=='BULLISH':
        stop=min([x.lower for x in (fvg,block) if x is not None] or [last])
        risk=last-stop
        target=last+2*risk if risk>0 else last
    else:
        stop=max([x.upper for x in (fvg,block) if x is not None] or [last])
        risk=stop-last
        target=last-2*risk if risk>0 else last
    rr=abs(target-last)/abs(last-stop) if abs(last-stop)>0 else 0
    setup=score_setup(structure=structure,sweep=sweep,fvg=fvg,order_block=block,rr=rr,config=config)
    if setup.score < min_score or setup.action=='NONE': return None
    return {'action':setup.action,'entry':last,'stop_loss':stop,'target':target,'risk_reward':rr,'confidence':setup.confidence/100.0,'score':setup.score,'reasons':list(setup.reasons),'entry_zone_low':setup.entry_zone_low,'entry_zone_high':setup.entry_zone_high}
