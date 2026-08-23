import pytest

from app.risk_sizing import calculate_position_size


def test_position_size_respects_risk_budget_and_lot_size():
    result = calculate_position_size(
        equity=100000,
        risk_percent=1,
        entry=100,
        stop=95,
        lot_size=10,
    )
    assert result.quantity == 200
    assert result.risk_amount == 1000
    assert result.notional == 20000


def test_notional_cap_can_reduce_quantity():
    result = calculate_position_size(
        equity=100000,
        risk_percent=5,
        entry=100,
        stop=90,
        lot_size=10,
        max_notional_percent=2,
    )
    assert result.quantity == 20
    assert result.notional == 2000


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        calculate_position_size(equity=100000, risk_percent=1, entry=100, stop=100)
    with pytest.raises(ValueError):
        calculate_position_size(equity=100000, risk_percent=1, entry=100, stop=95, lot_size=0)
    with pytest.raises(ValueError):
        calculate_position_size(equity=100000, risk_percent=1, entry=100, stop=95, max_notional_percent=0)
