import pytest

from app.reconciliation import ReconciliationEngine


def check(i, b):
    return ReconciliationEngine().check([], [], i, b)


def test_same_long_position_is_clean():
    r = check([{"symbol": "NIFTY", "quantity": 10, "side": "BUY"}], [{"symbol": "NIFTY", "quantity": 10, "side": "BUY"}])
    assert r.ok


def test_same_short_position_is_clean():
    r = check([{"symbol": "NIFTY", "quantity": 10, "side": "SELL"}], [{"symbol": "NIFTY", "quantity": 10, "side": "SELL"}])
    assert r.ok


def test_long_vs_short_with_same_absolute_quantity_is_drift():
    r = check([{"symbol": "NIFTY", "quantity": 10, "side": "BUY"}], [{"symbol": "NIFTY", "quantity": 10, "side": "SELL"}])
    assert not r.ok
    assert r.trading_halted
    assert r.position_drift[0]["internal_signed_quantity"] == 10
    assert r.position_drift[0]["broker_signed_quantity"] == -10


def test_explicit_signed_quantity_is_supported():
    r = check([{"symbol": "NIFTY", "signed_quantity": -10}], [{"symbol": "NIFTY", "signed_quantity": -10}])
    assert r.ok


def test_unknown_position_side_fails_closed():
    with pytest.raises(ValueError, match="unknown position side"):
        check([{"symbol": "NIFTY", "quantity": 10, "side": "UNKNOWN"}], [{"symbol": "NIFTY", "quantity": 10, "side": "UNKNOWN"}])
