import pytest

from app.position_manager import PositionManager


def test_reconcile_accepts_signed_long_position():
    manager = PositionManager()
    manager.open("NIFTY", "BUY", 5, 100)

    result = manager.reconcile([{"symbol": "NIFTY", "quantity": 5}])

    assert result == {"ok": True, "drift": []}


def test_reconcile_accepts_signed_short_position():
    manager = PositionManager()
    manager.open("NIFTY", "SELL", 5, 100)

    result = manager.reconcile([{"symbol": "NIFTY", "quantity": -5}])

    assert result == {"ok": True, "drift": []}


def test_reconcile_blocks_short_sign_mismatch():
    manager = PositionManager()
    manager.open("NIFTY", "SELL", 5, 100)

    result = manager.reconcile([{"symbol": "NIFTY", "quantity": 5}])

    assert result["ok"] is False
    assert result["drift"] == [
        {"symbol": "NIFTY", "internal_quantity": -5.0, "broker_quantity": 5.0}
    ]


def test_reconcile_detects_broker_only_position():
    manager = PositionManager()

    result = manager.reconcile([{"symbol": "BANKNIFTY", "quantity": 10}])

    assert result["ok"] is False
    assert result["drift"] == [
        {"symbol": "BANKNIFTY", "internal_quantity": 0.0, "broker_quantity": 10.0}
    ]


def test_reconcile_ignores_zero_broker_only_position():
    manager = PositionManager()

    result = manager.reconcile([{"symbol": "BANKNIFTY", "quantity": 0}])

    assert result == {"ok": True, "drift": []}


def test_reconcile_rejects_duplicate_broker_symbols():
    manager = PositionManager()

    with pytest.raises(ValueError, match="duplicate broker position"):
        manager.reconcile([
            {"symbol": "NIFTY", "quantity": 5},
            {"symbol": "nifty", "quantity": 5},
        ])


def test_reconcile_rejects_missing_symbol():
    manager = PositionManager()

    with pytest.raises(ValueError, match="missing symbol"):
        manager.reconcile([{"quantity": 5}])
