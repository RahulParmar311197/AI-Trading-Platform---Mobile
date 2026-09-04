from types import SimpleNamespace

import pytest

from app.execution import ExecutionResult, OrderStatus
from app.order_intent import OrderIntent
from app.portfolio import PaperPortfolio


def order(symbol="NIFTY", side="BUY"):
    return OrderIntent(symbol, side, 100.0, 95.0 if side == "BUY" else 105.0, 110.0 if side == "BUY" else 90.0, 1.0, 5.0, "TEST", 0.8)


def fill(quantity=1.0, price=100.0, commission=1.0, slippage=0.5):
    return ExecutionResult("PAPER-1", OrderStatus.FILLED, quantity, price, "paper fill", commission, slippage)


def test_apply_fill_rejects_duplicate_symbol_instead_of_overwriting_position():
    portfolio = PaperPortfolio(10000.0)
    portfolio.apply_fill(order(), fill())
    with pytest.raises(RuntimeError, match="overwrite"):
        portfolio.apply_fill(order(), fill(price=101.0))
    assert portfolio.positions["NIFTY"].entry_price == 100.0


def test_apply_fill_rejects_non_finite_or_invalid_fill_values():
    portfolio = PaperPortfolio(10000.0)
    with pytest.raises(ValueError, match="finite"):
        portfolio.apply_fill(order(), fill(price=float("nan")))
    with pytest.raises(ValueError, match="invalid fill"):
        portfolio.apply_fill(order(), fill(commission=-1.0))


def test_position_unrealized_pnl_validates_mark_and_quantity():
    portfolio = PaperPortfolio(10000.0)
    position = portfolio.apply_fill(order(), fill(commission=0.0, slippage=0.0))
    with pytest.raises(ValueError):
        position.unrealized_pnl(float("nan"))
    with pytest.raises(ValueError):
        position.unrealized_pnl(101.0, 2.0)


def test_mark_fails_closed_when_any_open_position_lacks_a_price():
    portfolio = PaperPortfolio(10000.0)
    portfolio.apply_fill(order("NIFTY"), fill(commission=0.0, slippage=0.0))
    portfolio.apply_fill(order("BANKNIFTY"), fill(commission=0.0, slippage=0.0))
    with pytest.raises(ValueError, match="incomplete portfolio valuation"):
        portfolio.mark({"NIFTY": 101.0})


def test_process_ohlc_bar_rejects_malformed_range():
    portfolio = PaperPortfolio(10000.0)
    portfolio.apply_fill(order(), fill(commission=0.0, slippage=0.0))
    with pytest.raises(ValueError, match="invalid OHLC"):
        portfolio.process_ohlc_bar({"NIFTY": SimpleNamespace(high=98.0, low=99.0)})


def test_short_position_pnl_and_stop_are_directionally_correct():
    portfolio = PaperPortfolio(10000.0)
    portfolio.apply_fill(order("NIFTY", "SELL"), fill(commission=0.0, slippage=0.0))
    result = portfolio.process_bar({"NIFTY": 90.0})
    assert result[0].reason == "TAKE_PROFIT"
    assert result[0].realized_pnl == 10.0
