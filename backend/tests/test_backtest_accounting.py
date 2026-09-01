from app.backtest import Candle, CandleBacktester


def test_backtest_empty_candles_is_deterministic():
    result = CandleBacktester().run([])
    assert result.trades == []
    assert result.final_equity == 100000.0
    assert result.net_pnl == 0.0


def test_backtest_result_exposes_gross_and_net_pnl_consistently():
    candles = [
        Candle(timestamp=1, open=100, high=105, low=95, close=104),
        Candle(timestamp=2, open=104, high=110, low=100, close=109),
    ]
    result = CandleBacktester().run(candles)
    assert result.final_equity == 100000.0 + result.net_pnl
    assert result.net_pnl <= result.gross_pnl
    assert result.fees >= 0.0


def test_backtest_equity_curve_ends_at_final_equity():
    candles = [
        Candle(timestamp=1, open=100, high=101, low=99, close=100),
        Candle(timestamp=2, open=100, high=102, low=98, close=101),
        Candle(timestamp=3, open=101, high=103, low=100, close=102),
    ]
    result = CandleBacktester().run(candles)
    assert result.equity_curve
    assert result.equity_curve[-1] == result.final_equity
