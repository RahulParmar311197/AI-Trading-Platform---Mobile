import pytest

from app.backtest import Candle, CandleBacktester


def test_backtest_empty_candles_is_deterministic():
    result = CandleBacktester().run([])
    assert result.trades == ()
    assert result.final_equity == 100000.0
    assert result.equity_curve == (100000.0,)


def test_backtest_rejects_insufficient_candles():
    candles = [
        Candle(timestamp=index, open=100, high=101, low=99, close=100)
        for index in range(24)
    ]
    with pytest.raises(ValueError, match="insufficient candles"):
        CandleBacktester().run(candles)


def test_backtest_equity_curve_ends_at_final_equity_for_valid_input():
    candles = [
        Candle(timestamp=index, open=100 + index * 0.1, high=101 + index * 0.1, low=99 + index * 0.1, close=100 + index * 0.1)
        for index in range(25)
    ]
    result = CandleBacktester().run(candles)
    assert result.equity_curve
    assert result.equity_curve[-1] == result.final_equity
    assert result.final_equity == result.initial_equity
