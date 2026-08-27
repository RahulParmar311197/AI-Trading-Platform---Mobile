from datetime import datetime, timedelta, timezone

import pytest

from app.backtest_engine import run_backtest
from app.market_data import Candle


def candles(n=80):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(minutes=i),
            symbol="NIFTY",
            open=100 + i * 0.1,
            high=100.2 + i * 0.1,
            low=99.8 + i * 0.1,
            close=100.1 + i * 0.1,
            volume=1000,
        )
        for i in range(n)
    ]


def test_rejects_invalid_capital_and_risk():
    with pytest.raises(ValueError):
        run_backtest(candles(), starting_equity=0)
    with pytest.raises(ValueError):
        run_backtest(candles(), risk_percent=0)
    with pytest.raises(ValueError):
        run_backtest(candles(), risk_percent=6)


def test_rejects_negative_costs():
    with pytest.raises(ValueError, match="cost"):
        run_backtest(candles(), fee_bps=-1)
    with pytest.raises(ValueError, match="cost"):
        run_backtest(candles(), slippage_bps=-1)


def test_produces_risk_and_performance_metrics():
    result = run_backtest(candles())
    assert result["starting_equity"] == 100000.0
    assert "ending_equity" in result
    assert "net_pnl" in result
    assert "max_drawdown_percent" in result
    assert "trade_journal" in result
    assert result["trades"] == len(result["trade_journal"])


def test_ml_mode_requires_predictor_and_artifact():
    with pytest.raises(ValueError, match="ML predictor"):
        run_backtest(candles(), enable_ml=True)
