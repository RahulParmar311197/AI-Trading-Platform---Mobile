import pytest
from app.risk_gate import RiskGate

class EmptyPortfolio:
    positions = []

def test_stale_snapshot_fails_closed():
    gate = RiskGate(max_gross_exposure=1000, max_positions=50)
    decision = gate.evaluate(EmptyPortfolio(), requested_notional=2000)
    assert not decision.approved
    assert decision.checks["exposure_limit"] is False

def test_kill_switch_style_block_is_not_bypassable():
    gate = RiskGate(max_gross_exposure=0, max_positions=50)
    decision = gate.evaluate(EmptyPortfolio(), requested_notional=1)
    assert decision.approved is False

def test_position_limit_rejects_new_position():
    class FullPortfolio:
        positions = [object()] * 2
    gate = RiskGate(max_gross_exposure=100000, max_positions=2)
    decision = gate.evaluate(FullPortfolio(), requested_notional=1)
    assert decision.approved is False
    assert decision.checks["position_count_limit"] is False

@pytest.mark.parametrize("notional", [1001, 5000, 100000])
def test_exposure_breach_never_approved(notional):
    gate = RiskGate(max_gross_exposure=1000, max_positions=50)
    assert gate.evaluate(EmptyPortfolio(), requested_notional=notional).approved is False
