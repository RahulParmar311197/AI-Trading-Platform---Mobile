from datetime import datetime, timezone

import pytest

from app.broker_order_lifecycle import InvalidOrderTransition, OrderLifecycle, OrderLifecycleEvent, OrderStatus


def event(status, filled=0):
    return OrderLifecycleEvent(status, datetime.now(timezone.utc), filled_quantity=filled)


def test_partial_fill_lifecycle():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED))
    lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 3))
    lifecycle.apply(event(OrderStatus.FILLED, 5))
    assert lifecycle.status is OrderStatus.FILLED
    assert lifecycle.filled_quantity == 5
    assert lifecycle.terminal


def test_terminal_order_cannot_transition():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED))
    lifecycle.apply(event(OrderStatus.FILLED, 5))
    with pytest.raises(InvalidOrderTransition):
        lifecycle.apply(event(OrderStatus.CANCELLED, 5))


def test_filled_quantity_cannot_decrease():
    lifecycle = OrderLifecycle()
    lifecycle.apply(event(OrderStatus.ACCEPTED))
    lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 5))
    with pytest.raises(InvalidOrderTransition, match="decrease"):
        lifecycle.apply(event(OrderStatus.PARTIALLY_FILLED, 2))
