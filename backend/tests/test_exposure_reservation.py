from app.broker_adapter import BrokerOrderRequest
from app.risk_gate import ExposureReservationBook, PreTradeRiskGate, RiskLimits, RiskSnapshot


def req(order_id, side="BUY", quantity=10):
    return BrokerOrderRequest(client_order_id=order_id, symbol="NIFTY", side=side, quantity=quantity)


def gate():
    return PreTradeRiskGate(RiskLimits(10, 10, 1000, 200), ExposureReservationBook())


def test_second_order_is_rejected_against_existing_reservation():
    risk = gate()
    snapshot = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("a"), snapshot).allowed
    decision = risk.reserve(req("b"), snapshot)
    assert not decision.allowed
    assert decision.reason == "RISK_EXPOSURE_RESERVATION"


def test_same_order_replay_is_idempotent():
    risk = gate()
    snapshot = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("a"), snapshot).allowed
    assert risk.reserve(req("a"), snapshot).allowed


def test_released_reservation_allows_next_order():
    risk = gate()
    snapshot = RiskSnapshot(position_quantity=0, broker_ready=True)
    assert risk.reserve(req("a"), snapshot).allowed
    risk.release("a")
    assert risk.reserve(req("b"), snapshot).allowed


def test_reducing_position_can_reserve_while_other_side_is_not_allowed():
    risk = gate()
    snapshot = RiskSnapshot(position_quantity=10, broker_ready=True)
    assert risk.reserve(req("reduce", side="SELL", quantity=10), snapshot).allowed
    assert not risk.reserve(req("add", side="BUY", quantity=1), snapshot).allowed
