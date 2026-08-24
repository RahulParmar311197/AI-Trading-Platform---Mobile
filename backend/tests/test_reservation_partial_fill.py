from app.broker_adapter import BrokerOrderRequest
from app.risk_gate import ExposureReservationBook, PreTradeRiskGate, RiskLimits, RiskSnapshot


def req(order_id, quantity=10):
    return BrokerOrderRequest(client_order_id=order_id, symbol="NIFTY", side="BUY", quantity=quantity)


def test_partial_fill_releases_only_filled_reservation():
    risk = PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), ExposureReservationBook())
    snap = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("pf", 10), snap).allowed
    risk.adjust_reservation("pf", filled_quantity=4)
    decision = risk.reserve(req("next", 7), snap)
    assert not decision.allowed
    assert risk.reserve(req("next-small", 6), snap).allowed


def test_full_fill_releases_reservation():
    risk = PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), ExposureReservationBook())
    snap = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("full", 10), snap).allowed
    risk.adjust_reservation("full", filled_quantity=10)
    assert risk.reserve(req("next", 10), snap).allowed


def test_cancel_after_partial_fill_releases_remaining_reservation():
    risk = PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), ExposureReservationBook())
    snap = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("cancel", 10), snap).allowed
    risk.adjust_reservation("cancel", filled_quantity=4)
    risk.release("cancel")
    assert risk.reserve(req("next", 10), snap).allowed
