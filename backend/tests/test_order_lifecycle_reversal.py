from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_sell_overshoot_closes_long_and_opens_remaining_short():
    lifecycle = OrderLifecycle()
    lifecycle.create("buy", "NIFTY", "BUY", 10)
    lifecycle.transition("buy", OrderStatus.FILLED, filled_quantity=10, fill_price=100)

    lifecycle.create("sell", "NIFTY", "SELL", 15)
    lifecycle.transition("sell", OrderStatus.FILLED, filled_quantity=15, fill_price=110)

    position = lifecycle.positions["NIFTY"]
    assert position.side == "SELL"
    assert position.quantity == 5
    assert position.entry_price == 110


def test_buy_overshoot_closes_short_and_opens_remaining_long():
    lifecycle = OrderLifecycle()
    lifecycle.create("sell", "NIFTY", "SELL", 10)
    lifecycle.transition("sell", OrderStatus.FILLED, filled_quantity=10, fill_price=110)

    lifecycle.create("buy", "NIFTY", "BUY", 15)
    lifecycle.transition("buy", OrderStatus.FILLED, filled_quantity=15, fill_price=100)

    position = lifecycle.positions["NIFTY"]
    assert position.side == "BUY"
    assert position.quantity == 5
    assert position.entry_price == 100


def test_exact_opposite_fill_closes_position_without_reversal():
    lifecycle = OrderLifecycle()
    lifecycle.create("buy", "NIFTY", "BUY", 10)
    lifecycle.transition("buy", OrderStatus.FILLED, filled_quantity=10, fill_price=100)

    lifecycle.create("sell", "NIFTY", "SELL", 10)
    lifecycle.transition("sell", OrderStatus.FILLED, filled_quantity=10, fill_price=110)

    assert "NIFTY" not in lifecycle.positions
