from datetime import datetime, timedelta, timezone
from app.backtest_v2 import run_backtest_v2
from app.market_data import Candle
from app.execution_costs import ExecutionCostModel


def candle(i, close, high=None, low=None):
    ts=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i)
    return Candle(symbol='NIFTY',timestamp=ts,open=close,high=high if high is not None else close,low=low if low is not None else close,close=close,volume=1000)


def test_backtest_v2_returns_required_accounting_fields():
    candles=[candle(i,100+i*0.1) for i in range(30)]
    result=run_backtest_v2(candles,execution_costs=ExecutionCostModel(commission_bps=1,slippage_bps=1,fixed_fee=1))
    for key in ('starting_equity','ending_equity','realized_pnl','equity_curve','trade_journal','total_commission','total_slippage'):
        assert key in result
    assert len(result['equity_curve']) == len(candles)


def test_backtest_v2_costs_are_non_negative():
    candles=[candle(i,100) for i in range(30)]
    result=run_backtest_v2(candles,execution_costs=ExecutionCostModel(commission_bps=5,slippage_bps=2,fixed_fee=1))
    assert result['total_commission'] >= 0
    assert result['total_slippage'] >= 0
