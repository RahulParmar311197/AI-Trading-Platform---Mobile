import pytest

from app.instrument_constraints import InstrumentConstraints


def test_price_off_tick_is_rejected_instead_of_rounded():
    constraints = InstrumentConstraints(tick_size=0.05, quantity_step=1)
    with pytest.raises(ValueError, match="price is not aligned"):
        constraints.normalize_price(100.03)


def test_quantity_off_step_is_rejected_instead_of_rounded():
    constraints = InstrumentConstraints(tick_size=0.05, quantity_step=25)
    with pytest.raises(ValueError, match="quantity is not aligned"):
        constraints.normalize_quantity(26)


def test_max_quantity_is_rejected_instead_of_clamped():
    constraints = InstrumentConstraints(tick_size=0.05, quantity_step=25, max_quantity=100)
    with pytest.raises(ValueError, match="quantity exceeds instrument maximum"):
        constraints.normalize_quantity(125)


def test_aligned_price_and_quantity_are_preserved_exactly():
    constraints = InstrumentConstraints(tick_size=0.05, quantity_step=25, min_quantity=25)
    assert constraints.normalize_price(100.15) == 100.15
    assert constraints.normalize_quantity(50, price=100.15) == 50


def test_invalid_constraint_metadata_fails_closed():
    with pytest.raises(ValueError, match="tick_size must be positive and finite"):
        InstrumentConstraints(tick_size=0).validate()
    with pytest.raises(ValueError, match="quantity_step must be positive and finite"):
        InstrumentConstraints(quantity_step=float("nan")).validate()
