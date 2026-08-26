from app.broker_adapter import BrokerOrderRequest
from app.order_lifecycle import OrderStatus
from app.risk_gate import ExposureReservationBook, PreTradeRiskGate, RiskLimits, RiskSnapshot


def request(cid, side="BUY", qty=10):
    return BrokerOrderRequest(client_order_id=cid, symbol="RELIANCE", side=side, quantity=qty)


def gate(max_position=100):
    return PreTradeRiskGate(RiskLimits(100, max_position, 100000, 100000))


def snapshot(position=0):
    return RiskSnapshot(position_quantity=position, broker_ready=True)


def test_buy_and_sell_reservations_are_signed_and_idempotent():
    g = gate()
    assert g.reserve(request("b1", "BUY", 20), snapshot()).allowed
    assert g.reservations.get("b1") == 20
    assert g.reserve(request("b1", "BUY", 20), snapshot()).allowed
    assert g.reserve(request("s1", "SELL", 10), snapshot()).allowed
    assert g.reservations.snapshot() == {"b1": 20, "s1": -10}


def test_reservations_respect_combined_position_limit():
    g = gate(50)
    assert g.reserve(request("b1", "BUY", 30), snapshot()).allowed
    assert not g.reserve(request("b2", "BUY", 25), snapshot()).allowed


def test_partial_fill_reduces_reservation_and_final_fill_releases_it():
    g = gate()
    r = request("b1", "BUY", 20)
    assert g.reserve(r, snapshot()).allowed
    assert g.update_after_fill(r, 7, 7).allowed
    assert g.reservations.get("b1") == 13
    assert g.update_after_fill(r, 20, 20).allowed
    assert g.reservations.get("b1") is None


def test_terminal_release_is_idempotent():
    g = gate()
    r = request("b1", "BUY", 20)
    assert g.reserve(r, snapshot()).allowed
    g.release("b1")
    g.release("b1")
    assert g.reservations.get("b1") is None


def test_rebuild_uses_only_unfinished_remaining_quantity():
    class Order:
        def __init__(self, status, qty, filled, side):
            self.status = status
            self.quantity = qty
            self.filled_quantity = filled
            self.side = side

    class Lifecycle:
        orders = {
            "open": Order(OrderStatus.NEW, 20, 5, "BUY"),
            "filled": Order(OrderStatus.FILLED, 20, 20, "BUY"),
            "cancelled": Order(OrderStatus.CANCELLED, 20, 0, "SELL"),
        }

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(Lifecycle())
    assert book.snapshot() == {"open": 15}
