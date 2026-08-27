from datetime import datetime, timedelta, timezone

from app.backtest_engine import run_backtest
from app.market_data import Candle


def make_candles(n=90):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    out = []
    for i in range(n):
        price += 0.2
        out.append(Candle(start + timedelta(minutes=i), "NIFTY", "1m", price - .1, price + .2, price - .2, price, 1000 + i))
    return out


def test_ai_strategy_mode_runs_through_existing_simulator():
    result = run_backtest(
        make_candles(),
        strategy_mode="ai",
        ai_symbol="NIFTY",
        ai_timeframe="1m",
    )
    assert result["strategy_mode"] == "ai"
    assert "trade_journal" in result
    assert "equity_curve" in result
