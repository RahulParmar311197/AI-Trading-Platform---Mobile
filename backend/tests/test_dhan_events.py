import pytest

from app.broker_events import BrokerEventType
from app.brokers.dhan_events import normalize_dhan_order


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("TRANSIT", BrokerEventType.SUBMITTED),
        ("PENDING", BrokerEventType.ACKNOWLEDGED),
        ("PART_TRADED", BrokerEventType.PARTIALLY_FILLED),
        ("TRADED", BrokerEventType.FILLED),
        ("REJECTED", BrokerEventType.REJECTED),
        ("CANCELLED", BrokerEventType.CANCELLED),
        ("EXPIRED", BrokerEventType.UNKNOWN),
        ("NEW_STATUS", BrokerEventType.UNKNOWN),
    ],
)
def test_dhan_status_mapping(status, expected):
    event = normalize_dhan_order({"orderId": "D1", "orderStatus": status})
    assert event.event_type is expected


def test_dhan_partial_fill_and_price():
    event = normalize_dhan_order(
        {
            "orderId": "D2",
            "orderStatus": "PART_TRADED",
            "filled_qty": 3,
            "averageTradedPrice": 125.5,
        }
    )
    assert event.filled_quantity == 3
    assert event.fill_price == 125.5


def test_dhan_requires_order_id():
    with pytest.raises(ValueError):
        normalize_dhan_order({"orderStatus": "TRADED"})


def test_dhan_rejects_invalid_fill_values():
    with pytest.raises(ValueError):
        normalize_dhan_order(
            {
                "orderId": "D3",
                "orderStatus": "FILLED",
                "filled_qty": "bad",
                "averageTradedPrice": 100,
            }
        )


def test_dhan_event_id_is_deterministic_when_missing():
    payload = {"orderId": "D4", "orderStatus": "TRADED", "filled_qty": 1, "averageTradedPrice": 10}
    first = normalize_dhan_order(payload)
    second = normalize_dhan_order(payload)
    assert first.event_id == second.event_id
