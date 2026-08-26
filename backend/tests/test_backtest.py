from datetime import datetime, timedelta, timezone

from app.backtest import BacktestConfig, CandleBacktester
from app.market_data import Candle


def candles(count=25):
    start = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)
    return [Candle(timestamp=start + timedelta(minutes=i), symbol="TEST", timeframe="5m", open=100+i, high=102+i, low=99+i, close=101+i, volume=1000) for i in range(count)]


def test_empty_backtest_is_deterministic():
    result = CandleBacktester().run([])
    assert result.final_equity == result.initial_equity
    assert result.trades == ()


def test_backtest_applies_configured_fee_and_slippage():
    result = CandleBacktester(BacktestConfig(fee_bps=10, slippage_bps=5, signal_min_score=999)).run(candles())
    assert result.final_equity == result.initial_equity
    assert result.trades == ()


def test_backtest_returns_equity_curve():
    result = CandleBacktester(BacktestConfig(signal_min_score=999)).run(candles())
    assert result.equity_curve
    assert result.equity_curve[0] == result.initial_equity
