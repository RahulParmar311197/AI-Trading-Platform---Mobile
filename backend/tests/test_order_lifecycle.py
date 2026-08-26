from app.order_lifecycle import OrderLifecycle, OrderStatus
import pytest


def test_full_order_lifecycle_opens_and_closes_position():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.SUBMITTED); book.transition("o1", OrderStatus.FILLED, 10, 100.0)
    assert book.orders["o1"].status == OrderStatus.FILLED and book.positions["NIFTY"].quantity == 10
    book.create("o2", "NIFTY", "SELL", 10); book.transition("o2", OrderStatus.FILLED, 10, 110.0); assert "NIFTY" not in book.positions


def test_partial_fill_is_tracked():
    book = OrderLifecycle(); book.create("o1", "BANKNIFTY", "BUY", 10); book.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 500.0)
    assert book.orders["o1"].filled_quantity == 4 and book.orders["o1"].status == OrderStatus.PARTIALLY_FILLED and book.positions["BANKNIFTY"].quantity == 4


def test_partial_then_full_does_not_double_count_position():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 100.0); book.transition("o1", OrderStatus.FILLED, 10, 102.0)
    assert book.positions["NIFTY"].quantity == 10 and book.orders["o1"].applied_fill_quantity == 10
    book.transition("o1", OrderStatus.FILLED, 10, 102.0); assert book.positions["NIFTY"].quantity == 10


def test_execution_fill_events_use_weighted_average_price():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.apply_fill("o1", 4, 100.0, "f1"); book.apply_fill("o1", 3, 101.0, "f2"); book.apply_fill("o1", 3, 102.0, "f3")
    assert book.orders["o1"].status == OrderStatus.FILLED and book.orders["o1"].filled_quantity == 10 and book.orders["o1"].average_fill_price == pytest.approx(101.0) and book.positions["NIFTY"].entry_price == pytest.approx(101.0)


def test_execution_fill_replay_by_id_cannot_double_apply():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.apply_fill("o1", 4, 100.0, "f1"); book.apply_fill("o1", 4, 100.0, "f1")
    assert book.orders["o1"].filled_quantity == 4 and book.positions["NIFTY"].quantity == 4


def test_average_fill_price_reconciliation_applies_only_new_quantity():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 100.0); book.transition("o1", OrderStatus.FILLED, 10, 104.0)
    assert book.positions["NIFTY"].entry_price == pytest.approx(104.0)


def test_invalid_fill_rejected():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10)
    with pytest.raises(ValueError): book.transition("o1", OrderStatus.FILLED, 11, 100.0)


def test_fill_quantity_cannot_move_backwards():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.PARTIALLY_FILLED, 6, 100.0)
    with pytest.raises(ValueError, match="move backwards"): book.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 100.0)


def test_ambiguous_submission_moves_to_pending_reconciliation_without_filling():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.SUBMISSION_INTENT)
    order = book.mark_pending_reconciliation("o1", "BROKER_TIMEOUT")
    assert order.status == OrderStatus.PENDING_RECONCILIATION
    assert order.filled_quantity == 0
    assert "NIFTY" not in book.positions


def test_pending_reconciliation_can_be_resolved_by_broker_fill():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.SUBMISSION_INTENT); book.mark_pending_reconciliation("o1", "BROKER_TIMEOUT")
    book.transition("o1", OrderStatus.FILLED, 10, 100.0)
    assert book.orders["o1"].status == OrderStatus.FILLED
    assert book.positions["NIFTY"].quantity == 10


def test_terminal_order_cannot_be_marked_pending_reconciliation():
    book = OrderLifecycle(); book.create("o1", "NIFTY", "BUY", 10); book.transition("o1", OrderStatus.REJECTED)
    with pytest.raises(ValueError, match="terminal order"):
        book.mark_pending_reconciliation("o1")
