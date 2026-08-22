from datetime import datetime, timedelta, timezone
from app.market_data import Candle
from app.smc_structure import detect_swings, detect_structure, StructureEvent


def c(i,o,h,l,cl):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),o,h,l,cl,1000)


def test_detects_unique_swing_high_and_low():
    candles=[c(0,100,101,99,100),c(1,100,102,99,101),c(2,101,110,100,109),c(3,109,103,98,100),c(4,100,102,90,95),c(5,95,99,92,97),c(6,97,100,94,99)]
    swings=detect_swings(candles,1,1)
    assert any(s.kind=='HIGH' and s.index==2 for s in swings)
    assert any(s.kind=='LOW' and s.index==4 for s in swings)


def test_bullish_break_after_bearish_structure_is_choch():
    candles=[c(0,100,102,99,101),c(1,101,103,98,99),c(2,99,100,95,96),c(3,96,98,94,95),c(4,95,105,94,104),c(5,104,108,101,107)]
    signals=detect_structure(candles, detect_swings(candles,1,1))
    assert any(s.event in (StructureEvent.BOS,StructureEvent.CHOCH) for s in signals)
