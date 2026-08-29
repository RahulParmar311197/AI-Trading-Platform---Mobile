import math

import pytest

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType


def _event(**overrides):
    values = {
        "event_id": "evt-1",
        "broker_order_id": "broker-1",
        "client_order_id": "client-1",
        "symbol": "NSE_EQ|INE002A01018",
        "side": "BUY",
        "event_type": CanonicalExecutionEventType.FILLED,
        "quantity": 10.0,
        "price": 100.0,
    }
    values.update(overrides)
    return CanonicalExecutionEvent(**values)


def test_rejects_non_finite_quantity():
    for quantity in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            _event(quantity=quantity)


def test_rejects_non_finite_price():
    for price in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            _event(price=price)


def test_accepts_finite_zero_quantity_for_non_fill_events():
    event = _event(event_type=CanonicalExecutionEventType.SUBMITTED, quantity=0.0, price=None)
    assert event.quantity == 0.0
