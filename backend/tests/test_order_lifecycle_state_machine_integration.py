import pytest

from app.order_lifecycle import OrderLifecycle, OrderStatus


def test_submission_intent_to_partial_to_filled():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("ord-1", "NIFTY", "BUY", 10)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.SUBMITTED)
    lifecycle.apply_fill(order.order_id, 4, 100.0, fill_id="fill-1")
    lifecycle.apply_fill(order.order_id, 6, 101.0, fill_id="fill-2")
    assert lifecycle.orders[order.order_id].status == OrderStatus.FILLED
    assert lifecycle.orders[order.order_id].filled_quantity == 10


def test_ambiguous_submission_reconciles_to_open():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("ord-2", "NIFTY", "BUY", 10)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.PENDING_RECONCILIATION)
    lifecycle.transition(order.order_id, OrderStatus.SUBMITTED)
    assert lifecycle.orders[order.order_id].status == OrderStatus.SUBMITTED


def test_duplicate_fill_is_idempotent():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("ord-3", "NIFTY", "BUY", 5)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.SUBMITTED)
    lifecycle.apply_fill(order.order_id, 5, 100.0, fill_id="same-fill")
    lifecycle.apply_fill(order.order_id, 5, 100.0, fill_id="same-fill")
    assert lifecycle.orders[order.order_id].filled_quantity == 5


def test_illegal_terminal_transition_is_rejected():
    lifecycle = OrderLifecycle()
    order = lifecycle.create("ord-4", "NIFTY", "BUY", 1)
    lifecycle.transition(order.order_id, OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition(order.order_id, OrderStatus.SUBMITTED)
    lifecycle.apply_fill(order.order_id, 1, 100.0, fill_id="fill-4")
    with pytest.raises(ValueError):
        lifecycle.transition(order.order_id, OrderStatus.SUBMITTED)
