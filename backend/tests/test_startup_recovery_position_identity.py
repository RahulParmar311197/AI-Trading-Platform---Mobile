import pytest

from app.startup_recovery import StartupRecoveryCoordinator


def test_duplicate_broker_position_symbol_fails_closed():
    positions = [
        {"symbol": "NIFTY", "side": "BUY", "quantity": 50},
        {"symbol": "NIFTY", "side": "BUY", "quantity": 25},
    ]

    with pytest.raises(ValueError, match="duplicate broker position symbol: NIFTY"):
        StartupRecoveryCoordinator._position_map(positions)


def test_distinct_broker_positions_are_preserved_by_identity():
    positions = [
        {"symbol": "NIFTY", "side": "BUY", "quantity": 50},
        {"tradingsymbol": "BANKNIFTY", "side": "SELL", "quantity": 25},
    ]

    assert StartupRecoveryCoordinator._position_map(positions) == {
        "NIFTY": 50.0,
        "BANKNIFTY": -25.0,
    }
