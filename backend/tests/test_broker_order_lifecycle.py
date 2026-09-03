from datetime import datetime, timedelta, timezone

import pytest

from app.broker_order_lifecycle import InvalidOrderTransition, OrderLifecycle, OrderLifecycleEvent, OrderStatus


def event(status, filled=0, broker_order_id=None, timestamp=None):
    return OrderLifecycleEvent(
        status,
        timestamp or datetime.now(timezone.utc),
        broker_order_id=broker_order_id,
        filled_quantity=filled,
    )


def test_partial_fill_lifecycle():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id="BO-1"))
    lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 3, broker_order_id="BO-1"))
    lifecycle.apply(event(OrderStatus.FILLED, 5, broker_order_id="BO-1"))
    assert lifecycle.status is OrderStatus.FILLED
    assert lifecycle.filled_quantity == 5
    assert lifecycle.broker_order_id == "BO-1"
    assert lifecycle.terminal


def test_terminal_order_cannot_transition():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id="BO-1"))
    lifecycle.apply(event(OrderStatus.FILLED, 5, broker_order_id="BO-1"))
    with pytest.raises(InvalidOrderTransition):
        lifecycle.apply(event(OrderStatus.CANCELLED, 5, broker_order_id="BO-1"))


def test_filled_quantity_cannot_decrease():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id="BO-1"))
    lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 5, broker_order_id="BO-1"))
    with pytest.raises(InvalidOrderTransition, match="decrease"):
        lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 2, broker_order_id="BO-1"))


def test_broker_order_id_cannot_change_mid_lifecycle():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id="BO-1"))
    with pytest.raises(InvalidOrderTransition, match="broker order id cannot change"):
        lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 1, broker_order_id="BO-2"))
    assert lifecycle.status is OrderStatus.ACCEPTED
    assert lifecycle.broker_order_id == "BO-1"
    assert lifecycle.filled_quantity == 0


def test_broker_order_id_cannot_be_blank():
    lifecycle = OrderLifecycle()
    with pytest.raises(InvalidOrderTransition, match="broker order id must be non-empty"):
        lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id="   "))
    assert lifecycle.broker_order_id is None


def test_lifecycle_can_bind_broker_id_on_first_event_and_omit_later():
    lifecycle = OrderLifecycle()
    first = datetime.now(timezone.utc)
    lifecycle.apply(event(OrderStatus.ACCEPTED, broker_order_id=" BO-1 ", timestamp=first))
    lifecycle.apply(
        event(
            OrderStatus.PARTIALLY_FILLED,
            2,
            timestamp=first + timedelta(seconds=1),
        )
    )
    assert lifecycle.broker_order_id == "BO-1"
    assert lifecycle.filled_quantity == 2
