import pytest

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType


@pytest.mark.parametrize("field", ["event_id", "broker_order_id", "client_order_id"])
def test_whitespace_only_event_identity_is_rejected(field):
    values = {
        "event_id": "e1",
        "broker_order_id": "b1",
        "client_order_id": "c1",
        "symbol": "NIFTY",
        "side": "BUY",
        "event_type": CanonicalExecutionEventType.SUBMITTED,
    }
    values[field] = "   "
    with pytest.raises(ValueError, match="event_id, broker_order_id and client_order_id are required"):
        CanonicalExecutionEvent(**values)


def test_non_whitespace_event_id_remains_accepted():
    event = CanonicalExecutionEvent(
        " e1 ",
        " b1 ",
        " c1 ",
        "NIFTY",
        "BUY",
        CanonicalExecutionEventType.SUBMITTED,
    )
    assert event.event_id == " e1 "
    assert event.broker_order_id == " b1 "
    assert event.client_order_id == " c1 "
