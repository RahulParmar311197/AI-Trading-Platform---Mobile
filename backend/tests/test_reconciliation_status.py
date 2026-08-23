from app.reconciliation import ReconciliationEngine, normalize_order_status


def test_common_broker_statuses_normalize_to_platform_states():
    assert normalize_order_status("OPEN") == "SUBMITTED"
    assert normalize_order_status("NEW") == "SUBMITTED"
    assert normalize_order_status("PART_TRADED") == "PARTIALLY_FILLED"
    assert normalize_order_status("TRADED") == "FILLED"
    assert normalize_order_status("COMPLETE") == "FILLED"
    assert normalize_order_status("CANCELED") == "CANCELLED"
    assert normalize_order_status("FAILED") == "REJECTED"


def test_open_and_submitted_are_not_false_drift():
    result = ReconciliationEngine().check(
        [{"client_order_id": "o1", "status": "SUBMITTED"}],
        [{"client_order_id": "o1", "status": "OPEN"}],
        [],
        [],
    )
    assert result.ok
    assert not result.trading_halted


def test_traded_and_filled_are_not_false_drift():
    result = ReconciliationEngine().check(
        [{"client_order_id": "o1", "status": "FILLED"}],
        [{"client_order_id": "o1", "status": "TRADED"}],
        [],
        [],
    )
    assert result.ok


def test_real_status_mismatch_still_halts():
    result = ReconciliationEngine().check(
        [{"client_order_id": "o1", "status": "SUBMITTED"}],
        [{"client_order_id": "o1", "status": "FILLED"}],
        [],
        [],
    )
    assert not result.ok
    assert result.trading_halted
