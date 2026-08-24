from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciler, BrokerOrder, ReconciliationAction


def test_missing_remote_order_is_created_locally():
    book = OrderLifecycle()
    events = OrderReconciler(book).reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1")
    ])
    assert events[0].action == ReconciliationAction.CREATE
    assert book.orders["c1"].broker_order_id == "b1"
    assert book.orders["c1"].filled_quantity == 10


def test_duplicate_broker_update_is_alerted():
    book = OrderLifecycle()
    remote = BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1")
    events = OrderReconciler(book).reconcile([remote, remote])
    assert events[1].action == ReconciliationAction.ALERT


def test_already_synced_order_is_noop():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    book.transition("c1", OrderStatus.FILLED, 10, 100.0)
    events = OrderReconciler(book).reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1")
    ])
    assert events[0].action == ReconciliationAction.NOOP


def test_repeated_cumulative_partial_updates_do_not_double_apply_position():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    reconciler = OrderReconciler(book)

    first = reconciler.reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1")
    ])
    second = reconciler.reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1")
    ])

    assert first[0].action == ReconciliationAction.UPDATE
    assert second[0].action == ReconciliationAction.NOOP
    assert book.orders["c1"].filled_quantity == 4
    assert book.orders["c1"].applied_fill_quantity == 4
    assert book.positions["NIFTY"].quantity == 4


def test_later_cumulative_fill_applies_only_the_delta():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    reconciler = OrderReconciler(book)

    reconciler.reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1")
    ])
    reconciler.reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 110.0, "c1")
    ])

    assert book.orders["c1"].filled_quantity == 10
    assert book.orders["c1"].applied_fill_quantity == 10
    assert book.positions["NIFTY"].quantity == 10
    assert book.positions["NIFTY"].entry_price == 110.0


def test_identity_mismatch_is_alerted_without_mutating_local_state():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    reconciler = OrderReconciler(book)

    events = reconciler.reconcile([
        BrokerOrder("b1", "BANKNIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1")
    ])

    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_SYMBOL_MISMATCH"
    assert book.orders["c1"].filled_quantity == 0
    assert "NIFTY" not in book.positions


def test_broker_quantity_mismatch_is_alerted():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([
        BrokerOrder("b1", "NIFTY", "BUY", 11, OrderStatus.FILLED, 11, 100.0, "c1")
    ])
    assert events[0].action == ReconciliationAction.ALERT
