from app.reconciliation import ReconciliationEngine


def check(i, b):
    return ReconciliationEngine().check(i, b, [], [])


def test_equal_partial_fill_is_clean():
    r = check(
        [{"client_order_id": "o1", "status": "PARTIALLY_FILLED", "quantity": 10, "filled_quantity": 4}],
        [{"client_order_id": "o1", "status": "PART_TRADED", "quantity": 10, "filled_quantity": 4}],
    )
    assert r.ok


def test_fill_quantity_mismatch_halts():
    r = check(
        [{"client_order_id": "o1", "status": "PARTIALLY_FILLED", "quantity": 10, "filled_quantity": 4}],
        [{"client_order_id": "o1", "status": "PART_TRADED", "quantity": 10, "filled_quantity": 5}],
    )
    assert not r.ok
    assert r.trading_halted
    assert r.order_drift[0]["reason"] == "FILLED_QUANTITY_MISMATCH"


def test_broker_overfill_halts():
    r = check(
        [{"client_order_id": "o1", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [{"client_order_id": "o1", "status": "COMPLETE", "quantity": 10, "filled_quantity": 11}],
    )
    assert not r.ok
    assert r.order_drift[0]["reason"] in {"FILLED_QUANTITY_MISMATCH", "BROKER_OVERFILL"}


def test_filled_order_requires_full_quantity():
    r = check(
        [{"client_order_id": "o1", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [{"client_order_id": "o1", "status": "COMPLETE", "quantity": 10, "filled_quantity": 9}],
    )
    assert not r.ok


def test_same_full_fill_is_clean():
    r = check(
        [{"client_order_id": "o1", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [{"client_order_id": "o1", "status": "TRADED", "quantity": 10, "filled_quantity": 10}],
    )
    assert r.ok
