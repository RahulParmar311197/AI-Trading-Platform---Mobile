from datetime import datetime, timedelta, timezone
from app.market_data import Candle
from app.smc_structure import SwingPoint
from app.ict_liquidity import detect_equal_liquidity, detect_liquidity_sweeps


def c(i,o,h,l,cl):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),o,h,l,cl,1000)


def test_detects_equal_high_buy_side_liquidity():
    pools=detect_equal_liquidity([SwingPoint(2,100,'HIGH'),SwingPoint(5,100.05,'HIGH')],tolerance=0.001)
    assert len(pools)==1 and pools[0].kind=='BUY_SIDE'


def test_detects_buy_side_liquidity_sweep():
    pools=detect_equal_liquidity([SwingPoint(1,100,'HIGH'),SwingPoint(3,100,'HIGH')],0.001)
    candles=[c(0,99,100,98,99),c(1,99,100,98,99),c(2,99,99,97,98),c(3,98,100,97,99),c(4,99,102,98,99)]
    sweeps=detect_liquidity_sweeps(candles,pools)
    assert any(s.kind=='BUY_SIDE_SWEEP' for s in sweeps)
