from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_partial_fills_are_applied_incrementally_without_double_counting():
    lifecycle = OrderLifecycle()
    lifecycle.create("pf-1", "NIFTY", "BUY", 10)

    lifecycle.transition("pf-1", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.transition("pf-1", OrderStatus.PARTIALLY_FILLED, filled_quantity=7, fill_price=101)
    lifecycle.transition("pf-1", OrderStatus.FILLED, filled_quantity=10, fill_price=102)

    order = lifecycle.orders["pf-1"]
    position = lifecycle.positions["NIFTY"]
    assert order.filled_quantity == 10
    assert order.applied_fill_quantity == 10
    assert position.quantity == 10
    assert position.entry_price > 100


def test_replaying_same_partial_fill_does_not_change_position():
    lifecycle = OrderLifecycle()
    lifecycle.create("pf-2", "BANKNIFTY", "BUY", 5)
    lifecycle.transition("pf-2", OrderStatus.PARTIALLY_FILLED, filled_quantity=3, fill_price=200)
    before = (lifecycle.positions["BANKNIFTY"].quantity, lifecycle.orders["pf-2"].applied_fill_quantity)
    lifecycle.transition("pf-2", OrderStatus.PARTIALLY_FILLED, filled_quantity=3, fill_price=200)
    after = (lifecycle.positions["BANKNIFTY"].quantity, lifecycle.orders["pf-2"].applied_fill_quantity)
    assert after == before


def test_invalid_fill_cannot_exceed_order_quantity():
    lifecycle = OrderLifecycle()
    lifecycle.create("pf-3", "NIFTY", "BUY", 2)
    try:
        lifecycle.transition("pf-3", OrderStatus.PARTIALLY_FILLED, filled_quantity=3, fill_price=100)
        assert False, "expected invalid fill quantity to be rejected"
    except ValueError as exc:
        assert "invalid filled quantity" in str(exc)
