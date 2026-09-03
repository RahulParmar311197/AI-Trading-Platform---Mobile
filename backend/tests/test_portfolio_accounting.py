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
    assert portfolio.equity == 100982.0


def test_short_position_pnl_direction():
    portfolio=PaperPortfolio(100000)
    portfolio.apply_fill(make_order('SELL'), make_fill('SELL', 100.0))
    result=portfolio.close_position('NIFTY', 90.0, 'TAKE_PROFIT')
    assert result.realized_pnl == 1000.0


def test_entry_and_exit_commission_are_each_charged_once():
    portfolio = PaperPortfolio(100000.0)
    portfolio.apply_fill(make_order(), make_fill(quantity=10.0, commission=3.0))
    result = portfolio.close_position('NIFTY', 108.0, 'TAKE_PROFIT', commission=4.0)

    gross_trade_pnl = (108.0 - 100.0) * 10.0
    expected_final_equity = 100000.0 + gross_trade_pnl - 3.0 - 4.0

    assert result.realized_pnl == gross_trade_pnl - 4.0
    assert portfolio.realized_pnl == gross_trade_pnl - 4.0
    assert portfolio.equity == expected_final_equity
    assert portfolio.total_commission == 7.0


def test_marked_equity_includes_unrealized_pnl_and_entry_fee_once():
    portfolio = PaperPortfolio(100000.0)
    portfolio.apply_fill(make_order(), make_fill(quantity=10.0, commission=3.0))

    marked = portfolio.mark({'NIFTY': 105.0})

    assert marked['realized_pnl'] == 0.0
    assert marked['unrealized_pnl'] == 50.0
    assert marked['equity'] == 100047.0
    assert marked['total_commission'] == 3.0
