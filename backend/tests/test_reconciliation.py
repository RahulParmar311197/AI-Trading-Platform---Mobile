import pytest

from app.reconciliation import ReconciliationEngine, ReconciliationCheckResult


def test_order_missing_and_unknown_are_detected_and_halt_trading():
    engine = ReconciliationEngine()
    result = engine.check(
        [{"client_order_id": "1", "status": "PENDING"}],
        [{"broker_order_id": "2", "status": "PENDING"}],
        [], [],
    )
    assert not result.ok
    assert result.trading_halted
    assert {item["id"] for item in result.order_drift} == {"1", "2"}


def test_order_status_mismatch_is_detected():
    result = ReconciliationEngine().check(
        [{"client_order_id": "1", "status": "PENDING"}],
        [{"broker_order_id": "1", "status": "TRADED"}],
        [], [],
    )
    assert not result.ok
    assert result.order_drift[0]["id"] == "1"


def test_position_quantity_mismatch_is_detected():
    result = ReconciliationEngine().check(
        [], [],
        [{"symbol": "NIFTY", "quantity": 10}],
        [{"symbol": "NIFTY", "quantity": 5}],
    )
    assert not result.ok
    assert result.position_drift[0]["symbol"] == "NIFTY"


def test_matching_state_is_clean():
    result = ReconciliationEngine().check(
        [{"client_order_id": "1", "status": "PENDING"}],
        [{"broker_order_id": "1", "status": "PENDING"}],
        [{"symbol": "NIFTY", "quantity": 10}],
        [{"symbol": "NIFTY", "quantity": 10}],
    )
    assert result.ok
    assert not result.trading_halted


def test_halt_cannot_be_cleared_from_failed_reconciliation():
    engine = ReconciliationEngine()
    failed = engine.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [])
    with pytest.raises(ValueError, match="cannot be cleared"):
        engine.reset_halt(failed)
    assert engine.trading_halted


def test_halt_can_only_be_cleared_from_authenticated_clean_check():
    engine = ReconciliationEngine()
    failed = engine.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [])
    assert failed.trading_halted
    clean = engine.check([], [], [], [])
    assert clean.ok
    assert engine.reset_halt(clean) == {"trading_halted": False}
    assert not engine.trading_halted


def test_forged_reconciliation_result_cannot_clear_halt():
    engine = ReconciliationEngine()
    engine.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [])
    forged = object.__new__(ReconciliationCheckResult)
    object.__setattr__(forged, "ok", True)
    object.__setattr__(forged, "trading_halted", False)
    object.__setattr__(forged, "order_drift", [])
    object.__setattr__(forged, "position_drift", [])
    object.__setattr__(forged, "checked_at", "forged")
    object.__setattr__(forged, "_verification_token", object())
    with pytest.raises(ValueError, match="authenticated"):
        engine.reset_halt(forged)
    assert engine.trading_halted
