from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_restart_reconciles_fill_into_local_lifecycle():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-fill-1", "NIFTY", "BUY", 10)

    # Broker reports a 6-lot fill while the application was offline.
    lifecycle.transition("offline-fill-1", OrderStatus.PARTIALLY_FILLED, filled_quantity=6, fill_price=100)

    order = lifecycle.orders["offline-fill-1"]
    position = lifecycle.positions["NIFTY"]
    assert order.filled_quantity == 6
    assert order.applied_fill_quantity == 6
    assert position.quantity == 6


def test_restart_reconciles_completed_fill_without_double_counting():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-fill-2", "BANKNIFTY", "BUY", 5)
    lifecycle.transition("offline-fill-2", OrderStatus.FILLED, filled_quantity=5, fill_price=200)

    before = lifecycle.positions["BANKNIFTY"].quantity
    lifecycle.transition("offline-fill-2", OrderStatus.FILLED, filled_quantity=5, fill_price=200)
    after = lifecycle.positions["BANKNIFTY"].quantity

    assert before == 5
    assert after == before


def test_offline_partial_fill_then_final_fill_reaches_exact_order_quantity():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-fill-3", "NIFTY", "BUY", 10)
    lifecycle.transition("offline-fill-3", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.transition("offline-fill-3", OrderStatus.FILLED, filled_quantity=10, fill_price=101)

    order = lifecycle.orders["offline-fill-3"]
    assert order.filled_quantity == 10
    assert order.applied_fill_quantity == 10
    assert lifecycle.positions["NIFTY"].quantity == 10
