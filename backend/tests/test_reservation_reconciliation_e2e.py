from app.broker_adapter import BrokerOrderRequest
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.risk_gate import ExposureReservationBook, PreTradeRiskGate, RiskLimits, RiskSnapshot


def test_partial_fill_rebuild_preserves_only_remaining_quantity():
    lifecycle = OrderLifecycle()
    request = BrokerOrderRequest(client_order_id="reconcile-1", symbol="NIFTY", side="BUY", quantity=10)
    lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
    lifecycle.transition(request.client_order_id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.get("reconcile-1") == 6


def test_restart_rebuild_does_not_reserve_completed_order():
    lifecycle = OrderLifecycle()
    request = BrokerOrderRequest(client_order_id="reconcile-2", symbol="NIFTY", side="BUY", quantity=10)
    lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
    lifecycle.transition(request.client_order_id, OrderStatus.FILLED, filled_quantity=10, fill_price=100)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.get("reconcile-2") is None


def test_partial_fill_then_cancel_rebuilds_no_stale_reservation():
    lifecycle = OrderLifecycle()
    request = BrokerOrderRequest(client_order_id="reconcile-3", symbol="NIFTY", side="BUY", quantity=10)
    lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
    lifecycle.transition(request.client_order_id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)
    lifecycle.transition(request.client_order_id, OrderStatus.CANCELLED)

    book = ExposureReservationBook()
    book.rebuild_from_lifecycle(lifecycle)
    assert book.snapshot() == {}


def test_rebuilt_partial_reservation_still_enforces_position_limit():
    lifecycle = OrderLifecycle()
    request = BrokerOrderRequest(client_order_id="reconcile-4", symbol="NIFTY", side="BUY", quantity=10)
    lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
    lifecycle.transition(request.client_order_id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4, fill_price=100)

    risk = PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), ExposureReservationBook())
    risk.rebuild_from_lifecycle(lifecycle)
    snapshot = RiskSnapshot(position_quantity=4, broker_ready=True)
    assert not risk.reserve(BrokerOrderRequest(client_order_id="new", symbol="NIFTY", side="BUY", quantity=1), snapshot).allowed
