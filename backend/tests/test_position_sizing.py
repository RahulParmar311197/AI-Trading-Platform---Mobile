import pytest

from app.instruments import InstrumentSpec
from app.position_sizing import calculate_position_size


def spec(**kwargs):
    values = dict(symbol="NIFTY", security_id="NIFTY-TEST", exchange_segment="NSE_FO", lot_size=50, tick_size=0.05, multiplier=1.0, tradable=True)
    values.update(kwargs)
    return InstrumentSpec(**values)


def test_sizes_down_to_whole_lots():
    result = calculate_position_size(equity=100_000, risk_fraction=0.01, entry=100, stop=90, instrument=spec())
    assert result.quantity == 100
    assert result.risk_budget == 1000


def test_applies_max_quantity_as_whole_lots():
    result = calculate_position_size(equity=100_000, risk_fraction=0.10, entry=100, stop=90, instrument=spec(), max_quantity=125)
    assert result.quantity == 100


def test_rejects_insufficient_budget_for_one_lot():
    with pytest.raises(ValueError, match="insufficient"):
        calculate_position_size(equity=1_000, risk_fraction=0.01, entry=100, stop=99, instrument=spec())


def test_rejects_equal_entry_and_stop():
    with pytest.raises(ValueError, match="different"):
        calculate_position_size(equity=100_000, risk_fraction=0.01, entry=100, stop=100, instrument=spec())


def test_rejects_non_tradable_instrument():
    with pytest.raises(ValueError, match="not tradable"):
        calculate_position_size(equity=100_000, risk_fraction=0.01, entry=100, stop=90, instrument=spec(tradable=False))
