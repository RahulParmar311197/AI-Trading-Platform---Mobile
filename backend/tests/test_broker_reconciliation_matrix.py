import pytest
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import ExposureReservationBook

@pytest.mark.parametrize("status,filled,expected_position,expected_reservation", [
    (OrderStatus.OPEN, 0, 0, 10),
    (OrderStatus.PARTIALLY_FILLED, 4, 4, 6),
    (OrderStatus.FILLED, 10, 10, 0),
    (OrderStatus.CANCELLED, 0, 0, 0),
    (OrderStatus.REJECTED, 0, 0, 0),
])
def test_broker_state_reconciliation_matrix(status, filled, expected_position, expected_reservation):
    lifecycle = OrderLifecycle()
    lifecycle.create("matrix-1", "NIFTY", "BUY", 10)
    if status == OrderStatus.PARTIALLY_FILLED:
        lifecycle.transition("matrix-1", status, filled_quantity=filled, fill_price=100)
    elif status == OrderStatus.FILLED:
        lifecycle.transition("matrix-1", status, filled_quantity=filled, fill_price=100)
    else:
        lifecycle.transition("matrix-1", status)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert lifecycle.positions.get("NIFTY", type("P", (), {"quantity": 0})()).quantity == expected_position
    assert book.get("matrix-1") == (expected_reservation if expected_reservation else None)


def test_replayed_terminal_state_does_not_change_position_or_reservation():
    lifecycle = OrderLifecycle()
    lifecycle.create("matrix-2", "NIFTY", "BUY", 10)
    lifecycle.transition("matrix-2", OrderStatus.FILLED, filled_quantity=10, fill_price=100)
    before = lifecycle.positions["NIFTY"].quantity
    lifecycle.transition("matrix-2", OrderStatus.FILLED, filled_quantity=10, fill_price=100)
    assert lifecycle.positions["NIFTY"].quantity == before

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.snapshot() == {}
