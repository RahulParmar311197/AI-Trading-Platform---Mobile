from app.canonical_execution_event import CanonicalExecutionEventType
from app.execution_event_normalizer import ExecutionEventNormalizer


def test_normalizes_fill_payload():
    event = ExecutionEventNormalizer.normalize({
        "execution_id": "trade-1",
        "order_id": "broker-1",
        "client_id": "client-1",
        "tradingsymbol": "nifty",
        "transaction_type": "BUY",
        "status": "COMPLETE",
        "filled_quantity": 5,
        "price": 24500,
    }, broker="example")
    assert event.event_type is CanonicalExecutionEventType.FILLED
    assert event.symbol == "NIFTY"
    assert event.side == "BUY"
    assert event.quantity == 5
    assert event.price == 24500


def test_rejects_unknown_event_type():
    try:
        ExecutionEventNormalizer.normalize({"event_id": "x", "order_id": "o", "symbol": "NIFTY", "side": "BUY", "status": "UNKNOWN"}, broker="example")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unknown event type should fail closed")
