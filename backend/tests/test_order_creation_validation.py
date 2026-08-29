import math
import pytest

from app.order_lifecycle import OrderLifecycle


def test_order_creation_requires_positive_finite_quantity():
    book = OrderLifecycle()
    for quantity in (0, -1, float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="quantity"):
            book.create("o", "NIFTY", "BUY", quantity)


def test_order_creation_requires_supported_side():
    with pytest.raises(ValueError, match="side"):
        OrderLifecycle().create("o", "NIFTY", "HOLD", 1)


def test_order_creation_requires_nonempty_identity():
    book = OrderLifecycle()
    with pytest.raises(ValueError, match="order_id"):
        book.create(" ", "NIFTY", "BUY", 1)
    with pytest.raises(ValueError, match="symbol"):
        book.create("o", " ", "BUY", 1)


def test_order_creation_normalizes_identity_and_quantity():
    order = OrderLifecycle().create(" o1 ", " nifty ", " buy ", "2")
    assert order.order_id == " o1 "
    assert order.symbol == "NIFTY"
    assert order.side == "BUY"
    assert order.quantity == 2.0
    assert math.isfinite(order.quantity)
