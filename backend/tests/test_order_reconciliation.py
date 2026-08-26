from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciler, BrokerOrder, ReconciliationAction


def remote(order_id="b1", client_order_id="c1", account=7, route="upstox:account:7", **kwargs):
    return BrokerOrder(order_id, "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, client_order_id, account, route, **kwargs)


def test_missing_remote_order_is_created_locally_with_account_identity():
    book = OrderLifecycle()
    events = OrderReconciler(book).reconcile([remote()])
    assert events[0].action == ReconciliationAction.CREATE
    assert book.orders["c1"].broker_order_id == "b1"
    assert book.orders["c1"].filled_quantity == 10
    assert book.orders["c1"].broker_account_id == 7
    assert book.orders["c1"].broker_route == "upstox:account:7"


def test_broker_order_without_account_identity_is_not_materialized():
    book = OrderLifecycle()
    order = BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1")
    events = OrderReconciler(book).reconcile([order])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_ACCOUNT_IDENTITY_MISSING"
    assert "c1" not in book.orders


def test_duplicate_broker_update_is_alerted():
    book = OrderLifecycle()
    r = remote()
    events = OrderReconciler(book).reconcile([r, r])
    assert events[1].action == ReconciliationAction.ALERT


def test_already_synced_order_is_noop():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    book.transition("c1", OrderStatus.FILLED, 10, 100.0)
    events = OrderReconciler(book).reconcile([remote()])
    assert events[0].action == ReconciliationAction.NOOP


def test_broker_account_mismatch_is_alerted_without_mutating_local_state():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([remote(account=8, route="upstox:account:8")])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_ACCOUNT_ID_MISMATCH"
    assert book.orders["c1"].filled_quantity == 0
    assert "NIFTY" not in book.positions


def test_broker_route_mismatch_is_alerted_without_mutating_local_state():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([remote(route="upstox:account:99")])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_ROUTE_MISMATCH"
    assert book.orders["c1"].filled_quantity == 0


def test_repeated_cumulative_partial_updates_do_not_double_apply_position():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    reconciler = OrderReconciler(book)
    first = reconciler.reconcile([BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1", 7, "upstox:account:7")])
    second = reconciler.reconcile([BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1", 7, "upstox:account:7")])
    assert first[0].action == ReconciliationAction.UPDATE
    assert second[0].action == ReconciliationAction.NOOP
    assert book.orders["c1"].filled_quantity == 4
    assert book.positions["NIFTY"].quantity == 4


def test_later_cumulative_fill_applies_only_the_delta():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    reconciler = OrderReconciler(book)
    reconciler.reconcile([BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.PARTIALLY_FILLED, 4, 100.0, "c1", 7, "upstox:account:7")])
    reconciler.reconcile([BrokerOrder("b1", "NIFTY", "BUY", 10, OrderStatus.FILLED, 10, 110.0, "c1", 7, "upstox:account:7")])
    assert book.orders["c1"].filled_quantity == 10
    assert book.positions["NIFTY"].quantity == 10
    assert book.positions["NIFTY"].entry_price == 110.0


def test_identity_mismatch_is_alerted_without_mutating_local_state():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10)
    book.orders["c1"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([BrokerOrder("b1", "BANKNIFTY", "BUY", 10, OrderStatus.FILLED, 10, 100.0, "c1", 7, "upstox:account:7")])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_SYMBOL_MISMATCH"
    assert book.orders["c1"].filled_quantity == 0


def test_broker_quantity_mismatch_is_alerted():
    book = OrderLifecycle()
    book.create("c1", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["c1"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([BrokerOrder("b1", "NIFTY", "BUY", 11, OrderStatus.FILLED, 11, 100.0, "c1", 7, "upstox:account:7")])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason == "BROKER_QUANTITY_MISMATCH"


def test_multiple_local_orders_matching_one_broker_order_fail_closed():
    book = OrderLifecycle()
    book.create("local-a", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.create("local-b", "NIFTY", "BUY", 10, broker_account_id=7, broker_route="upstox:account:7")
    book.orders["local-a"].broker_order_id = "b1"
    book.orders["local-b"].broker_order_id = "b1"
    events = OrderReconciler(book).reconcile([remote(client_order_id=None)])
    assert events[0].action == ReconciliationAction.ALERT
    assert events[0].reason.startswith("AMBIGUOUS_BROKER_ORDER_IDENTITY:")
    assert book.orders["local-a"].filled_quantity == 0
    assert book.orders["local-b"].filled_quantity == 0
    assert "NIFTY" not in book.positions
