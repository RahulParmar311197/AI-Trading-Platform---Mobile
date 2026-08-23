from datetime import datetime, timedelta, timezone
from app.market_data import Candle
from app.ict_order_block import detect_order_blocks, order_block_state


def c(i,o,h,l,cl):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),o,h,l,cl,1000)


def test_detects_bullish_order_block():
    candles=[c(0,100,102,99,101),c(1,101,103,98,99),c(2,99,106,98,105)]
    blocks=detect_order_blocks(candles,0.005)
    assert len(blocks)==1 and blocks[0].kind=='BULLISH'
    assert blocks[0].origin_index==1


def test_detects_bearish_order_block():
    candles=[c(0,100,102,99,101),c(1,101,105,100,104),c(2,104,101,96,97)]
    blocks=detect_order_blocks(candles,0.005)
    assert len(blocks)==1 and blocks[0].kind=='BEARISH'


def test_order_block_mitigation():
    candles=[c(0,100,102,99,101),c(1,101,103,98,99),c(2,99,106,98,105),c(3,105,106,97,100)]
    block=detect_order_blocks(candles,0.005)[0]
    state=order_block_state(candles,block)
    assert state.mitigated is True
    assert state.mitigation_index==3
