from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import ExposureReservationBook


def test_offline_cancel_releases_reservation_after_restart():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-cancel-1", "NIFTY", "BUY", 10)
    lifecycle.transition("offline-cancel-1", OrderStatus.CANCELLED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)

    assert lifecycle.orders["offline-cancel-1"].status == OrderStatus.CANCELLED
    assert book.snapshot() == {}


def test_offline_expiry_is_terminal_and_not_rebuilt():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-expiry-1", "BANKNIFTY", "BUY", 5)
    # Broker/exchange expiry is represented by the terminal cancellation state.
    lifecycle.transition("offline-expiry-1", OrderStatus.CANCELLED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)

    assert lifecycle.orders["offline-expiry-1"].status == OrderStatus.CANCELLED
    assert book.get("offline-expiry-1") is None


def test_cancel_after_partial_fill_does_not_create_position_for_unfilled_quantity():
    lifecycle = OrderLifecycle()
    lifecycle.create("offline-cancel-2", "NIFTY", "BUY", 10)
    lifecycle.transition("offline-cancel-2", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.transition("offline-cancel-2", OrderStatus.CANCELLED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)

    assert lifecycle.positions["NIFTY"].quantity == 4
    assert book.snapshot() == {}
