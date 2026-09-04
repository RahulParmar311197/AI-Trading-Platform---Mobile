from datetime import datetime, timedelta, timezone

import pytest

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


def test_invalid_configuration_fails_closed():
    with pytest.raises(ValueError):
        CandleBacktester(BacktestConfig(initial_equity=float("nan")))
    with pytest.raises(ValueError):
        CandleBacktester(BacktestConfig(fee_bps=float("inf")))
    with pytest.raises(ValueError):
        CandleBacktester(BacktestConfig(signal_min_score=0))
    with pytest.raises(ValueError):
        CandleBacktester(BacktestConfig(signal_min_score=True))
    with pytest.raises(ValueError):
        CandleBacktester(BacktestConfig(freshness_seconds=-1))


def test_malformed_or_non_monotonic_input_is_rejected():
    data = candles()
    data[10], data[11] = data[11], data[10]
    with pytest.raises(ValueError):
        CandleBacktester().run(data)


def test_mixed_symbol_input_is_rejected():
    data = candles()
    data[-1] = Candle(timestamp=data[-1].timestamp, symbol="OTHER", timeframe="5m", open=100, high=102, low=99, close=101, volume=1000)
    with pytest.raises(ValueError):
        CandleBacktester().run(data)


def test_fill_price_rejects_invalid_side_or_price():
    backtester = CandleBacktester()
    with pytest.raises(ValueError):
        backtester._fill_price(100, "HOLD")
    with pytest.raises(ValueError):
        backtester._fill_price(float("nan"), "BUY")
    with pytest.raises(ValueError):
        backtester._fill_price(0, "BUY")
