import pytest

from app.broker_adapter import normalize_broker_update


@pytest.mark.parametrize(
    "raw_status, expected",
    [
        ("validation pending", "NEW"),
        ("modify pending", "NEW"),
        ("trigger pending", "NEW"),
        ("put order req received", "NEW"),
        ("open pending", "NEW"),
        ("not cancelled", "NEW"),
        ("not modified", "NEW"),
        ("modified", "NEW"),
        ("cancel pending", "NEW"),
        ("cancelled after market order", "CANCELLED"),
        ("cancelled", "CANCELLED"),
        ("rejected", "REJECTED"),
        ("complete", "FILLED"),
    ],
)
def test_upstox_statuses_map_to_canonical_lifecycle(raw_status, expected):
    quantity = 10
    filled = 0
    if expected == "FILLED":
        filled = quantity
    result = normalize_broker_update(
        {
            "order_id": "u1",
            "status": raw_status,
            "quantity": quantity,
            "filled_quantity": filled,
            "average_price": 100 if filled else None,
        }
    )
    assert result.status == expected


def test_upstox_open_with_partial_fill_becomes_partially_filled():
    result = normalize_broker_update(
        {
            "order_id": "u1",
            "status": "open",
            "quantity": 10,
            "filled_quantity": 4,
            "average_price": 100,
        }
    )
    assert result.status == "PARTIALLY_FILLED"
    assert result.filled_quantity == 4


def test_active_upstox_status_cannot_claim_full_fill():
    with pytest.raises(ValueError, match="active broker status cannot report a fully filled order"):
        normalize_broker_update(
            {
                "order_id": "u1",
                "status": "open",
                "quantity": 10,
                "filled_quantity": 10,
                "average_price": 100,
            }
        )


def test_unknown_upstox_status_fails_closed():
    with pytest.raises(ValueError, match="unsupported broker order status"):
        normalize_broker_update(
            {
                "order_id": "u1",
                "status": "some future broker status",
                "quantity": 10,
                "filled_quantity": 0,
            }
        )


def test_rejected_order_with_fill_fails_closed():
    with pytest.raises(ValueError, match="REJECTED broker status requires zero filled quantity"):
        normalize_broker_update(
            {
                "order_id": "u1",
                "status": "rejected",
                "quantity": 10,
                "filled_quantity": 1,
                "average_price": 100,
            }
        )
