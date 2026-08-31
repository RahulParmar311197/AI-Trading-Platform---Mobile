import pytest

from app.reconciliation import ReconciliationEngine, ReconciliationCheckResult


class _RecordingReservationStore:
    def __init__(self, failure: bool = False):
        self.calls = []
        self.failure = failure

    def reconcile_client_order(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise RuntimeError("reservation store unavailable")
        return "RELEASED"


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


def test_terminal_broker_order_releases_bound_reservation():
    reservations = _RecordingReservationStore()
    result = ReconciliationEngine(risk_reservation_store=reservations).check(
        [{"client_order_id": "client-1", "status": "SUBMITTED", "quantity": 10, "filled_quantity": 0}],
        [{"client_order_id": "client-1", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [], [],
    )
    assert not result.ok
    assert reservations.calls == [
        {"client_order_id": "client-1", "broker_status": "FILLED", "remaining_amount": None}
    ]


def test_partial_broker_order_reconciles_only_explicit_remaining_exposure():
    reservations = _RecordingReservationStore()
    result = ReconciliationEngine(risk_reservation_store=reservations).check(
        [{"client_order_id": "client-2", "status": "SUBMITTED", "quantity": 10, "filled_quantity": 0}],
        [{"client_order_id": "client-2", "status": "PARTIALLY_FILLED", "quantity": 10, "filled_quantity": 4, "remaining_exposure": 60}],
        [], [],
    )
    assert not result.ok
    assert reservations.calls[0]["client_order_id"] == "client-2"
    assert reservations.calls[0]["broker_status"] == "PARTIALLY_FILLED"
    assert reservations.calls[0]["remaining_amount"] == 60.0


def test_broker_order_without_client_identity_cannot_reconcile_reservation():
    reservations = _RecordingReservationStore()
    ReconciliationEngine(risk_reservation_store=reservations).check(
        [{"client_order_id": "client-3", "status": "SUBMITTED", "quantity": 10}],
        [{"broker_order_id": "broker-3", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [], [],
    )
    assert reservations.calls == []


def test_reservation_reconciliation_failure_halts_reconciliation():
    reservations = _RecordingReservationStore(failure=True)
    result = ReconciliationEngine(risk_reservation_store=reservations).check(
        [{"client_order_id": "client-4", "status": "SUBMITTED", "quantity": 10}],
        [{"client_order_id": "client-4", "status": "FILLED", "quantity": 10, "filled_quantity": 10}],
        [], [],
    )
    assert not result.ok
    assert result.trading_halted
    assert any(item["reason"] == "RISK_RESERVATION_RECONCILIATION_FAILED" for item in result.order_drift)


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
