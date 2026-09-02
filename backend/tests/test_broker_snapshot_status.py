import pytest

from app.broker_snapshot import canonical_order_status, dhan_snapshot


def test_unknown_broker_order_status_fails_closed():
    with pytest.raises(ValueError, match="unsupported broker order status"):
        canonical_order_status("MYSTERY_STATE")


def test_missing_broker_order_status_fails_closed():
    with pytest.raises(ValueError, match="broker order status is required"):
        canonical_order_status("")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETE", "FILLED"),
        ("EXECUTED", "FILLED"),
        ("CANCELED", "CANCELLED"),
        ("REJECTED", "REJECTED"),
        ("TRANSIT", "NEW"),
        ("OPEN", "NEW"),
        ("PARTIALLY_FILLED", "PARTIALLY_FILLED"),
    ],
)
def test_known_broker_order_statuses_normalize(raw, expected):
    assert canonical_order_status(raw) == expected


def test_dhan_snapshot_rejects_unknown_order_status_before_reconciliation():
    with pytest.raises(ValueError, match="unsupported broker order status"):
        dhan_snapshot(
            [{
                "orderId": "broker-1",
                "correlationId": "client-1",
                "orderStatus": "MYSTERY_STATE",
            }],
            [],
        )
