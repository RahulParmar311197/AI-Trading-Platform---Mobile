import pytest

from app.instrument_constraints import InstrumentConstraints


def test_price_rounds_down_to_tick():
    c = InstrumentConstraints(tick_size=0.05, quantity_step=1)
    assert c.normalize_price(100.079) == 100.05


def test_quantity_rounds_down_to_step():
    c = InstrumentConstraints(quantity_step=0.25, min_quantity=0.25)
    assert c.normalize_quantity(1.19) == 1.0


def test_quantity_below_minimum_rejected():
    c = InstrumentConstraints(quantity_step=1, min_quantity=5)
    with pytest.raises(ValueError, match="below instrument minimum"):
        c.normalize_quantity(4.9)


def test_max_quantity_caps():
    c = InstrumentConstraints(quantity_step=1, min_quantity=1, max_quantity=10)
    assert c.normalize_quantity(25) == 10


def test_min_notional_rejected():
    c = InstrumentConstraints(quantity_step=1, min_quantity=1, min_notional=1000)
    with pytest.raises(ValueError, match="minimum"):
        c.normalize_quantity(5, price=100)
