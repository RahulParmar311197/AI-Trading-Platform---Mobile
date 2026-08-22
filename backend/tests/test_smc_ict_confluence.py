from app.smc_ict_confluence import score_setup, ConfluenceConfig
from app.smc_structure import StructureSignal, StructureEvent
from app.ict_liquidity import LiquiditySweep
from app.ict_fvg import FairValueGap
from app.ict_order_block import OrderBlock


def test_high_confluence_bullish_setup():
    setup=score_setup(
        structure=StructureSignal(10,StructureEvent.CHOCH,'BULLISH',100,8),
        sweep=LiquiditySweep(11,'SELL_SIDE_SWEEP',95,97,True),
        fvg=FairValueGap(12,'BULLISH',98,101,99.5),
        order_block=OrderBlock(12,'BULLISH',96,99,11),
        rr=2.5,
    )
    assert setup.action=='BUY'
    assert setup.score==100
    assert 'LIQUIDITY_SWEEP' in setup.reasons
    assert 'FVG' in setup.reasons
    assert 'ORDER_BLOCK' in setup.reasons


def test_low_confluence_is_rejected():
    setup=score_setup(structure=None,sweep=None,fvg=None,order_block=None,rr=0,config=ConfluenceConfig(min_score=60))
    assert setup.action=='NONE'
    assert setup.score==0
