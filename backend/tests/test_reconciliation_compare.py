from app.order_lifecycle import OrderLifecycle
from app.reconciliation_compare import compare_broker_state


def test_matching_order_and_position_state_has_no_mismatches():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10, broker_order_id="broker-1")
    lifecycle.apply_fill("local-1", 10, 100)
    assert compare_broker_state(
        lifecycle,
        broker_orders=[{"order_id": "broker-1", "symbol": "NIFTY", "side": "BUY", "status": "FILLED"}],
        broker_positions=[{"symbol": "NIFTY", "quantity": 10, "side": "BUY"}],
    ) == []


def test_missing_local_order_at_broker_is_mismatch():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10, broker_order_id="broker-1")
    mismatches = compare_broker_state(lifecycle, broker_orders=[], broker_positions=[])
    assert any(m.domain == "orders" and "missing" in m.reason for m in mismatches)


def test_unowned_active_broker_order_is_mismatch():
    lifecycle = OrderLifecycle()
    mismatches = compare_broker_state(
        lifecycle,
        broker_orders=[{"order_id": "broker-9", "symbol": "NIFTY", "side": "BUY", "status": "OPEN"}],
        broker_positions=[],
    )
    assert any(m.identity == "broker-9" for m in mismatches)


def test_position_quantity_mismatch_is_fail_closed():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("local-1", 10, 100)
    mismatches = compare_broker_state(lifecycle, broker_orders=[], broker_positions=[{"symbol": "NIFTY", "quantity": 5, "side": "BUY"}])
    assert any(m.domain == "positions" for m in mismatches)


def test_reversal_sign_is_compared_correctly():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("local-1", 10, 100)
    lifecycle.create("local-2", "NIFTY", "SELL", 15)
    lifecycle.apply_fill("local-2", 15, 110)
    mismatches = compare_broker_state(lifecycle, broker_orders=[], broker_positions=[{"symbol": "NIFTY", "quantity": 5, "side": "SELL"}])
    assert mismatches == []
