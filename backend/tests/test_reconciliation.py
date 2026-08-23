from app.reconciliation import ReconciliationEngine


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


def test_halt_persists_until_explicit_reset():
    engine = ReconciliationEngine()
    engine.check([], [], [{"symbol": "NIFTY", "quantity": 1}], [])
    result = engine.check([], [], [], [])
    assert result.trading_halted
    assert engine.reset_halt() == {"trading_halted": False}
