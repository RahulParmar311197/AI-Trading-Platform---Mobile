from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_cumulative_average_fill_uses_incremental_execution_value():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)

    lifecycle.transition("o1", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.transition("o1", OrderStatus.FILLED, filled_quantity=10, fill_price=110)

    order = lifecycle.orders["o1"]
    position = lifecycle.positions["NIFTY"]

    assert order.applied_fill_quantity == 10
    assert order.applied_fill_value == 1100
    assert position.quantity == 10
    assert abs(position.entry_price - 110) < 1e-9


def test_cumulative_average_fill_does_not_double_count_partial_fill():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 10)

    lifecycle.transition("o1", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    first = lifecycle.positions["NIFTY"].entry_price
    lifecycle.transition("o1", OrderStatus.PARTIALLY_FILLED, filled_quantity=6, fill_price=105)

    position = lifecycle.positions["NIFTY"]
    assert first == 100
    assert position.quantity == 6
    assert abs(position.entry_price - 105) < 1e-9


def test_fill_price_cannot_be_non_positive():
    lifecycle = OrderLifecycle()
    lifecycle.create("o1", "NIFTY", "BUY", 1)
    try:
        lifecycle.transition("o1", OrderStatus.FILLED, filled_quantity=1, fill_price=0)
    except ValueError as exc:
        assert str(exc) == "fill price must be positive"
    else:
        raise AssertionError("non-positive fill price must be rejected")
