import pytest

from app.accounting import EquitySnapshot, calculate_equity


def test_equity_includes_realized_and_unrealized_pnl_and_costs():
    snapshot = EquitySnapshot(
        starting_equity=100000,
        realized_pnl=2000,
        unrealized_pnl=-500,
        fees=100,
        charges=50,
    )
    assert snapshot.net_pnl == pytest.approx(1350)
    assert snapshot.equity == pytest.approx(101350)


def test_calculate_equity_matches_snapshot():
    assert calculate_equity(
        starting_equity=50000,
        realized_pnl=-1000,
        unrealized_pnl=250,
        fees=50,
        charges=25,
    ) == pytest.approx(49175)


@pytest.mark.parametrize("field", ["starting_equity", "realized_pnl", "unrealized_pnl", "fees", "charges"])
def test_non_numeric_equity_input_is_rejected(field):
    values = dict(starting_equity=100000, realized_pnl=0, unrealized_pnl=0, fees=0, charges=0)
    values[field] = "not-a-number"
    with pytest.raises(ValueError, match=f"invalid {field}"):
        EquitySnapshot(**values).validate()


def test_negative_costs_are_rejected():
    with pytest.raises(ValueError, match="fees and charges cannot be negative"):
        EquitySnapshot(100000, fees=-1).validate()
