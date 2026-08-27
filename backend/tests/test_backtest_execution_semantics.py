from datetime import datetime, timedelta, timezone

from app.backtest_engine import run_backtest
from app.market_data import Candle


def _candles():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = []
    for i in range(55):
        price = 100 + i * 0.1
        values.append(Candle(start + timedelta(minutes=i), "NIFTY", price, price + 0.2, price - 0.2, price + 0.05, 1000))
    return values


def test_backtest_has_no_same_signal_bar_fill():
    candles = _candles()
    result = run_backtest(candles, strategy_mode="legacy")
    for trade in result["trade_journal"]:
        assert trade["bars"] >= 1


def test_backtest_reports_only_deterministic_exit_reasons():
    result = run_backtest(_candles(), strategy_mode="legacy")
    allowed = {"STOP_LOSS", "TAKE_PROFIT", "END_OF_TEST"}
    assert all(trade["reason"] in allowed for trade in result["trade_journal"])
