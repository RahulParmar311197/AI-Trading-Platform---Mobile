from datetime import datetime, timedelta, timezone
from app.backtest_v2 import run_backtest_v2
from app.market_data import Candle


def candle(i, close):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),close,close+0.5,close-0.5,close,1000)


def test_hybrid_strategy_is_supported():
    result=run_backtest_v2([candle(i,100+i*0.1) for i in range(30)],strategy='hybrid')
    assert result['strategy']=='hybrid'


def test_unknown_strategy_is_rejected():
    try:
        run_backtest_v2([candle(i,100) for i in range(30)],strategy='ensemble')
        assert False
    except ValueError:
        pass
