from datetime import datetime, timedelta, timezone
from app.backtest_v2 import run_backtest_v2
from app.market_data import Candle


def candle(i, close):
    return Candle('NIFTY',datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),close,close+0.5,close-0.5,close,1000)


def test_backtest_v2_embeds_metrics():
    result=run_backtest_v2([candle(i,100+i*0.1) for i in range(40)],strategy='smc_ict')
    assert 'metrics' in result
    assert result['metrics']['trade_count']==len(result['trade_journal'])
    assert result['metrics']['total_commission']==result['total_commission']
    assert result['metrics']['total_slippage']==result['total_slippage']
