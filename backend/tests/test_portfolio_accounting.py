from types import SimpleNamespace
from app.portfolio import PaperPortfolio
from app.order_intent import OrderIntent
from app.execution import ExecutionResult, OrderStatus


def make_order(side='BUY'):
    return OrderIntent('NIFTY', side, 100.0, 95.0 if side=='BUY' else 105.0, 110.0 if side=='BUY' else 90.0, 100.0, 500.0, 'test', 1.0)


def make_fill(side='BUY', price=100.0, quantity=100.0, commission=10.0, slippage=2.0):
    return ExecutionResult('TEST-1', OrderStatus.FILLED, quantity, price, 'test', commission, slippage)


def test_entry_cost_is_reflected_in_equity():
    portfolio=PaperPortfolio(100000)
    portfolio.apply_fill(make_order(), make_fill(commission=10, slippage=2))
    assert portfolio.total_commission == 10
    assert portfolio.total_slippage == 2
    assert portfolio.equity == 99990


def test_partial_close_reduces_quantity_and_moves_stop():
    portfolio=PaperPortfolio(100000)
    portfolio.apply_fill(make_order(), make_fill())
    result=portfolio.partial_close('NIFTY', 105.0, 50.0, True, commission=5.0, slippage=1.0)
    assert result.reason == 'PARTIAL_TP'
    assert result.quantity == 50
    assert portfolio.positions['NIFTY'].quantity == 50
    assert portfolio.positions['NIFTY'].stop_loss == 100.0
    assert result.realized_pnl == 245.0


def test_full_close_removes_position_and_records_net_pnl():
    portfolio=PaperPortfolio(100000)
    portfolio.apply_fill(make_order(), make_fill())
    result=portfolio.close_position('NIFTY', 110.0, 'TAKE_PROFIT', commission=8.0, slippage=2.0)
    assert result.realized_pnl == 992.0
    assert 'NIFTY' not in portfolio.positions
    assert portfolio.realized_pnl == 992.0
    assert portfolio.equity == 99982.0


def test_short_position_pnl_direction():
    portfolio=PaperPortfolio(100000)
    portfolio.apply_fill(make_order('SELL'), make_fill('SELL', 100.0))
    result=portfolio.close_position('NIFTY', 90.0, 'TAKE_PROFIT')
    assert result.realized_pnl == 1000.0
