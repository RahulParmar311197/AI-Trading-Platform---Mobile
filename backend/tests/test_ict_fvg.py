from datetime import datetime, timedelta, timezone
from app.market_data import Candle
from app.ict_fvg import detect_fvgs, fvg_state


def c(i,o,h,l,cl):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),o,h,l,cl,1000)


def test_detects_bullish_fvg():
    candles=[c(0,100,105,99,104),c(1,104,106,103,105),c(2,105,112,108,111)]
    gaps=detect_fvgs(candles)
    assert len(gaps)==1 and gaps[0].kind=='BULLISH'
    assert gaps[0].lower==105 and gaps[0].upper==108


def test_detects_bearish_fvg():
    candles=[c(0,100,105,99,104),c(1,104,106,103,105),c(2,105,101,97,98)]
    gaps=detect_fvgs(candles)
    assert len(gaps)==1 and gaps[0].kind=='BEARISH'


def test_fvg_mitigation_after_fill():
    candles=[c(0,100,105,99,104),c(1,104,106,103,105),c(2,105,112,108,111),c(3,111,109,104,106),c(4,106,107,104,105)]
    gap=detect_fvgs(candles)[0]
    state=fvg_state(candles,gap)
    assert state.mitigated is True
    assert state.fill_percent==1.0
