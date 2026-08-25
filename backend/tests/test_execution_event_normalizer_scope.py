import pytest

from app.execution_event_normalizer import ExecutionEventNormalizer


def _payload(**extra):
    value = {"event_id":"e1","broker_order_id":"b1","client_order_id":"c1","symbol":"NIFTY","side":"BUY","event_type":"FILLED","quantity":1,"price":100,"broker_account_id":7,"broker_route":"primary"}
    value.update(extra)
    return value


def test_normalizer_preserves_account_and_route():
    event = ExecutionEventNormalizer.normalize(_payload(), broker="upstox")
    assert event.broker_account_id == 7
    assert event.broker_route == "primary"


def test_account_without_route_is_rejected():
    with pytest.raises(ValueError, match="broker_route"):
        ExecutionEventNormalizer.normalize(_payload(broker_route=None), broker="upstox")


def test_invalid_account_is_rejected():
    with pytest.raises(ValueError, match="broker_account_id"):
        ExecutionEventNormalizer.normalize(_payload(broker_account_id=0), broker="upstox")
