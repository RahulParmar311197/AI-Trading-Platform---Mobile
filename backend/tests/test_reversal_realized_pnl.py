from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_reversal_preserves_realized_pnl_and_opens_residual_position():
    lifecycle = OrderLifecycle()
    lifecycle.create("buy", "NIFTY", "BUY", 10)
    lifecycle.transition("buy", OrderStatus.FILLED, filled_quantity=10, fill_price=100)

    lifecycle.create("sell", "NIFTY", "SELL", 15)
    lifecycle.transition("sell", OrderStatus.FILLED, filled_quantity=15, fill_price=110)

    assert lifecycle.realized_pnl_by_symbol["NIFTY"] == 100
    assert lifecycle.positions["NIFTY"].side == "SELL"
    assert lifecycle.positions["NIFTY"].quantity == 5
    assert lifecycle.positions["NIFTY"].entry_price == 110


def test_exact_close_keeps_realized_pnl_after_position_is_removed():
    lifecycle = OrderLifecycle()
    lifecycle.create("buy", "NIFTY", "BUY", 10)
    lifecycle.transition("buy", OrderStatus.FILLED, filled_quantity=10, fill_price=100)

    lifecycle.create("sell", "NIFTY", "SELL", 10)
    lifecycle.transition("sell", OrderStatus.FILLED, filled_quantity=10, fill_price=105)

    assert lifecycle.realized_pnl_by_symbol["NIFTY"] == 50
    assert "NIFTY" not in lifecycle.positions
