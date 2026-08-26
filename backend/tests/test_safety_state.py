from datetime import datetime, timedelta, timezone

import pytest

from app.broker_execution_context import BrokerExecutionContext
from app.reconciliation import ReconciliationEngine, ReconciliationCheckResult
from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyState, SafetyStateStore


def context(at: datetime, *, account_id: str = "acct-1", generation: int = 1, fingerprint: str = "fp-1") -> BrokerExecutionContext:
    return BrokerExecutionContext(account_id=account_id, broker_route="upstox", route_generation="route-1", generation=generation, snapshot_fingerprint=fingerprint, observed_at=at)


def verified_result(at: datetime, *, account_id: str = "acct-1", generation: int = 1, fingerprint: str = "fp-1") -> ReconciliationResult:
    engine = ReconciliationEngine()
    check = engine.check([], [], [], [])
    observed = datetime.fromisoformat(check.checked_at)
    if at < observed:
        at = observed
    execution_context = context(observed, account_id=account_id, generation=generation, fingerprint=fingerprint)
    return engine.build_verified_result(check, context=execution_context, reconciled_at=at, open_orders_reconciled=True, positions_reconciled=True, submission_intents_resolved=0, broker_ready=True)


def clear(store, result):
    return store.clear(result, active_context=result.context)


def test_halt_survives_restart(tmp_path):
    path = tmp_path / "safety.json"
    first = SafetyStateStore(str(path))
    halted = first.halt("BROKER_STATE_DRIFT")
    restored = SafetyStateStore(str(path)).load()
    assert restored.trading_halted is True
    assert restored.halt_reason == "BROKER_STATE_DRIFT"
    assert restored.halted_at == halted.halted_at
    assert restored.last_reconciliation_at is None


def test_clear_requires_verified_post_halt_reconciliation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    halted = store.halt("DRIFT")
    with pytest.raises(ValueError, match="verified reconciliation result"):
        store.clear(None, active_context=context(datetime.now(timezone.utc)))
    result = verified_result(halted.halted_at)
    with pytest.raises(RuntimeError, match="after the safety halt"):
        clear(store, result)
    reconciled_at = datetime.now(timezone.utc)
    cleared = clear(store, verified_result(reconciled_at))
    restored = store.load()
    assert cleared.trading_halted is False
    assert restored.trading_halted is False
    assert restored.halt_reason is None
    assert restored.halted_at is None
    assert restored.reconciliation_generation == 1
    assert restored.reconciliation_account_id == "acct-1"
    assert restored.broker_snapshot_fingerprint == "fp-1"


def test_drift_check_result_cannot_clear_safety_halt(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("DRIFT")
    check = ReconciliationEngine().check([], [], [], [])
    assert isinstance(check, ReconciliationCheckResult)
    with pytest.raises(ValueError, match="verified reconciliation result"):
        store.clear(check, active_context=context(datetime.now(timezone.utc)))


@pytest.mark.parametrize("field,value", [("account_id", "other"), ("generation", 2), ("fingerprint", "old-fp")])
def test_clear_rejects_mismatched_execution_context(tmp_path, field, value):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("DRIFT")
    result = verified_result(datetime.now(timezone.utc))
    kwargs = {"account_id": "acct-1", "generation": 1, "fingerprint": "fp-1", field: value}
    with pytest.raises(RuntimeError, match="context"):
        store.clear(result, active_context=context(result.context.observed_at, **kwargs))


def test_clear_rejects_missing_active_context(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("DRIFT")
    result = verified_result(datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="active broker execution context"):
        store.clear(result, active_context=None)


def test_context_rejects_naive_observation():
    with pytest.raises(ValueError, match="timezone-aware"):
        context(datetime.now())


def test_context_rejects_future_observation():
    with pytest.raises(ValueError, match="cannot be in the future"):
        context(datetime.now(timezone.utc) + timedelta(minutes=5))


def test_verified_result_rejects_future_reconciliation():
    with pytest.raises(ValueError, match="cannot be in the future"):
        verified_result(datetime.now(timezone.utc) + timedelta(minutes=5))


def test_missing_state_is_fail_open_for_uninitialized_store(tmp_path):
    state = SafetyStateStore(str(tmp_path / "missing.json")).load()
    assert state == SafetyState()


def test_corrupt_state_fails_closed(tmp_path):
    path = tmp_path / "safety.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid persisted safety state"):
        SafetyStateStore(str(path)).load()


def test_corrupt_primary_recovers_from_backup(tmp_path):
    path = tmp_path / "safety.json"
    store = SafetyStateStore(str(path))
    first = store.halt("FIRST_HALT")
    clear(store, verified_result(first.halted_at + timedelta(seconds=1)))
    store.halt("SECOND_HALT")
    path.write_text("{not-json", encoding="utf-8")
    restored = store.load()
    assert restored.trading_halted is False


def test_corrupt_primary_and_backup_fail_closed(tmp_path):
    path = tmp_path / "safety.json"
    store = SafetyStateStore(str(path))
    store.halt("DRIFT")
    path.write_text("{not-json", encoding="utf-8")
    store.backup_path.write_text("{also-not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid persisted safety state"):
        store.load()


def test_blank_halt_reason_rejected(tmp_path):
    with pytest.raises(ValueError, match="halt reason"):
        SafetyStateStore(str(tmp_path / "safety.json")).halt("  ")
