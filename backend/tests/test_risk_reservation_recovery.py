from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import ExposureReservationBook


def test_rebuild_uses_only_unresolved_remaining_quantity():
    lifecycle = OrderLifecycle()
    lifecycle.create("open", "NIFTY", "BUY", 10)
    lifecycle.transition("open", OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.create("done", "NIFTY", "BUY", 5)
    lifecycle.transition("done", OrderStatus.FILLED, filled_quantity=5, fill_price=101)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)

    assert book.get("open") == 6
    assert book.get("done") is None


def test_rebuild_survives_new_process_book():
    lifecycle = OrderLifecycle()
    lifecycle.create("pending", "NIFTY", "SELL", 7)

    first = ExposureReservationBook()
    first.rebuild_from_lifecycle(lifecycle)

    second = ExposureReservationBook()
    second.rebuild_from_lifecycle(lifecycle)

    assert first.snapshot() == {"pending": -7}
    assert second.snapshot() == {"pending": -7}


def test_partial_fill_update_releases_only_filled_exposure():
    lifecycle = OrderLifecycle()
    lifecycle.create("open", "NIFTY", "BUY", 10)
    lifecycle.transition("open", OrderStatus.SUBMITTED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.get("open") == 10

    lifecycle.transition("open", OrderStatus.PARTIALLY_FILLED, filled_quantity=6, fill_price=100)
    assert book.update("open", 4, current_position=6, max_position=10)
    assert book.get("open") == 4


def test_terminal_order_removes_reservation():
    book = ExposureReservationBook()
    assert book.reserve("o1", 5, 0, 10)
    book.release("o1")
    assert book.get("o1") is None
