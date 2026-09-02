import pytest

from app.broker_adapter import normalize_broker_update


def test_cancelled_order_can_preserve_partial_fill_for_reconciliation():
    result = normalize_broker_update({
        "order_id": "b1",
        "status": "CANCELLED",
        "quantity": 10,
        "filled_quantity": 4,
        "average_price": 100,
    })
    assert result.status == "CANCELLED"
    assert result.filled_quantity == 4
    assert result.average_price == 100


def test_cancelled_order_rejects_full_fill_instead_of_hiding_terminal_fill():
    with pytest.raises(ValueError, match="CANCELLED broker status"):
        normalize_broker_update({
            "order_id": "b1",
            "status": "CANCELLED",
            "quantity": 10,
            "filled_quantity": 10,
            "average_price": 100,
        })


def test_cancelled_partial_fill_requires_average_price():
    with pytest.raises(ValueError, match="cancelled broker order with a fill requires average_price"):
        normalize_broker_update({
            "order_id": "b1",
            "status": "CANCELLED",
            "quantity": 10,
            "filled_quantity": 4,
        })
