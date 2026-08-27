import pytest

from app.broker_reconciliation import reconcile_positions


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
