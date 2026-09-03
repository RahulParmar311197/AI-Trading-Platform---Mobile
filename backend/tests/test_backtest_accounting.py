from datetime import datetime, timedelta, timezone

import pytest

from app.backtest import Candle, CandleBacktester
from app.execution import ExecutionResult, OrderStatus
from app.order_intent import OrderIntent
from app.portfolio import PaperPortfolio


def _candle(index: int, price: float = 100.0) -> Candle:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index)
    return Candle(timestamp=timestamp, open=price, high=price + 1, low=price - 1, close=price, symbol="TEST")


def test_backtest_empty_candles_is_deterministic():
    result = CandleBacktester().run([])
    assert result.trades == ()
    assert result.final_equity == 100000.0
    assert result.equity_curve == (100000.0,)


def test_backtest_rejects_insufficient_candles():
    candles = [_candle(index) for index in range(24)]
    with pytest.raises(ValueError, match="insufficient candles"):
        CandleBacktester().run(candles)


def test_backtest_equity_curve_ends_at_final_equity_for_valid_input():
    candles = [_candle(index, 100 + index * 0.1) for index in range(25)]
    result = CandleBacktester().run(candles)
    assert result.equity_curve
    assert result.equity_curve[-1] == result.final_equity
    assert result.final_equity == result.initial_equity


def test_portfolio_trade_fee_invariant_deducts_entry_and_exit_once():
    portfolio = PaperPortfolio(100000.0)
    order = OrderIntent(
        symbol="TEST",
        side="BUY",
        entry=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        quantity=1.0,
        risk_amount=10.0,
        source="backtest",
        confidence=1.0,
    )
    entry_commission = 0.30
    exit_commission = 0.33
    fill = ExecutionResult("PAPER-1", OrderStatus.FILLED, 1.0, 100.0, "paper fill", entry_commission, 0.0)

    portfolio.apply_fill(order, fill)
    close = portfolio.close_position("TEST", 110.0, "TAKE_PROFIT", commission=exit_commission)

    expected_trade_pnl = (110.0 - 100.0) - entry_commission - exit_commission
    assert close.realized_pnl == pytest.approx(10.0 - exit_commission)
    assert portfolio.equity == pytest.approx(100000.0 + expected_trade_pnl)
    assert portfolio.total_commission == pytest.approx(entry_commission + exit_commission)
    assert close.realized_pnl - entry_commission == pytest.approx(expected_trade_pnl)
