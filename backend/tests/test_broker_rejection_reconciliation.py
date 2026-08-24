from app.broker_adapter import BrokerOrderRequest
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import ExposureReservationBook, PreTradeRiskGate, RiskLimits, RiskSnapshot


def test_broker_rejection_releases_reservation_and_is_terminal():
    lifecycle = OrderLifecycle()
    book = ExposureReservationBook()
    risk = PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), book)
    request = BrokerOrderRequest(client_order_id="reject-1", symbol="NIFTY", side="BUY", quantity=10)
    snapshot = RiskSnapshot(position_quantity=0, broker_ready=True)

    assert risk.reserve(request, snapshot).allowed
    lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
    lifecycle.transition(request.client_order_id, OrderStatus.REJECTED)
    risk.release(request.client_order_id)

    assert book.get(request.client_order_id) is None
    assert lifecycle.orders[request.client_order_id].status == OrderStatus.REJECTED


def test_rejected_order_is_not_rebuilt_after_restart():
    lifecycle = OrderLifecycle()
    lifecycle.create("reject-2", "BANKNIFTY", "BUY", 5)
    lifecycle.transition("reject-2", OrderStatus.REJECTED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.snapshot() == {}


def test_rejection_does_not_create_position():
    lifecycle = OrderLifecycle()
    lifecycle.create("reject-3", "NIFTY", "BUY", 5)
    lifecycle.transition("reject-3", OrderStatus.REJECTED)
    assert "NIFTY" not in lifecycle.positions
