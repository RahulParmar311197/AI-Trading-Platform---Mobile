from datetime import datetime, timedelta, timezone
from app.backtest_v2 import run_backtest_v2
from app.market_data import Candle


def candle(i, close):
    return Candle('NIFTY', datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i), close, close+0.5, close-0.5, close, 1000)


def test_strategy_selector_traditional():
    result=run_backtest_v2([candle(i,100+i*0.1) for i in range(30)], strategy='traditional')
    assert result['strategy']=='traditional'


def test_strategy_selector_smc_ict():
    result=run_backtest_v2([candle(i,100+i*0.1) for i in range(30)], strategy='smc_ict')
    assert result['strategy']=='smc_ict'


def test_strategy_selector_rejects_unknown_strategy():
    try:
        run_backtest_v2([candle(i,100) for i in range(30)], strategy='unknown')
        assert False
    except ValueError:
        pass
