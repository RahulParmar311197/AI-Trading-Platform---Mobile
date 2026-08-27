import pytest

from app.broker_reconciliation import (
    BrokerOrderSnapshot,
    LocalOrderSnapshot,
    OrderReconciler,
    reconcile_positions,
)


def test_positions_match_after_aggregation():
    report = reconcile_positions(
        [{"symbol": "NIFTY", "quantity": 1}, {"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "NIFTY", "quantity": 3}],
    )
    assert report.matched is True
    assert report.deltas == ()


def test_position_mismatch_is_reported():
    report = reconcile_positions(
        [{"symbol": "NIFTY", "quantity": 2}],
        [{"symbol": "NIFTY", "quantity": 5}],
    )
    assert report.matched is False
    assert report.deltas[0].delta == 3


def test_broker_only_and_local_only_are_explicit():
    report = reconcile_positions(
        [{"symbol": "BANKNIFTY", "quantity": 1}],
        [{"symbol": "NIFTY", "quantity": 1}],
    )
    assert report.matched is False
    assert report.broker_only == ("NIFTY",)
    assert report.local_only == ("BANKNIFTY",)


def test_tolerance_prevents_false_mismatch():
    report = reconcile_positions(
        [{"symbol": "NIFTY", "quantity": 1.0}],
        [{"symbol": "NIFTY", "quantity": 1.001}],
        quantity_tolerance=0.01,
    )
    assert report.matched is True


@pytest.mark.parametrize(
    "broker_row",
    [
        {"quantity": 1},
        {"symbol": "NIFTY"},
        {"symbol": "NIFTY", "quantity": float("nan")},
        {"symbol": "NIFTY", "quantity": float("inf")},
        {"symbol": "NIFTY", "quantity": "not-a-number"},
    ],
)
def test_malformed_broker_position_fails_closed(broker_row):
    with pytest.raises(ValueError):
        reconcile_positions([], [broker_row])


def test_malformed_local_position_fails_closed():
    with pytest.raises(ValueError):
        reconcile_positions([{"symbol": "NIFTY", "quantity": None}], [])


def _order(order_id="OID-1", *, quantity=10, filled_quantity=2, symbol="NIFTY", side="BUY", status="OPEN"):
    return LocalOrderSnapshot(order_id, symbol, side, quantity, filled_quantity, status)


def _broker(order_id="OID-1", *, quantity=10, filled_quantity=2, symbol="NIFTY", side="BUY", status="OPEN"):
    return BrokerOrderSnapshot(order_id, symbol, side, quantity, filled_quantity, status)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": float("nan")},
        {"quantity": float("inf")},
        {"quantity": -1},
        {"quantity": "not-a-number"},
        {"filled_quantity": float("nan")},
        {"filled_quantity": float("inf")},
        {"filled_quantity": -1},
        {"filled_quantity": 11},
    ],
)
def test_malformed_broker_order_fails_closed(kwargs):
    with pytest.raises(ValueError):
        OrderReconciler().reconcile({}, [_broker(**kwargs)])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": float("nan")},
        {"filled_quantity": float("inf")},
        {"filled_quantity": 11},
        {"side": ""},
        {"side": "HOLD"},
        {"symbol": ""},
        {"status": ""},
        {"order_id": ""},
    ],
)
def test_malformed_local_order_fails_closed(kwargs):
    with pytest.raises(ValueError):
        OrderReconciler().reconcile({"OID-1": _order(**kwargs)}, [])


def test_order_reconciliation_accepts_semantically_equivalent_status_aliases():
    issues = OrderReconciler().reconcile(
        {"OID-1": _order(status="FILLED", quantity=10, filled_quantity=10)},
        [_broker(status="COMPLETE", quantity=10, filled_quantity=10)],
    )
    assert issues == []


def test_order_reconciliation_accepts_cancelled_spelling_alias():
    issues = OrderReconciler().reconcile(
        {"OID-1": _order(status="CANCELLED", filled_quantity=0)},
        [_broker(status="CANCELED", filled_quantity=0)],
    )
    assert issues == []


def test_order_reconciliation_rejects_unsupported_broker_status():
    with pytest.raises(ValueError):
        OrderReconciler().reconcile({"OID-1": _order()}, [_broker(status="UNKNOWN_BROKER_STATE")])


def test_order_reconciliation_rejects_non_matching_mapping_key():
    with pytest.raises(ValueError):
        OrderReconciler().reconcile({"WRONG": _order()}, [_broker()])


def test_valid_orders_still_reconcile_cleanly():
    issues = OrderReconciler().reconcile({"OID-1": _order()}, [_broker()])
    assert issues == []
