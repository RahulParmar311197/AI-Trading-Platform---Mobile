from datetime import datetime, timedelta, timezone

import pytest

from app.safety_state import SafetyState, SafetyStateStore


def test_halt_survives_restart(tmp_path):
    path = tmp_path / "safety.json"
    first = SafetyStateStore(str(path))
    halted = first.halt("BROKER_STATE_DRIFT")

    restored = SafetyStateStore(str(path)).load()
    assert restored.trading_halted is True
    assert restored.halt_reason == "BROKER_STATE_DRIFT"
    assert restored.halted_at == halted.halted_at
    assert restored.last_reconciliation_at is None


def test_clear_requires_post_halt_reconciliation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    halted = store.halt("DRIFT")

    with pytest.raises(RuntimeError, match="post-halt broker reconciliation"):
        store.clear()

    with pytest.raises(RuntimeError, match="after the safety halt"):
        store.clear(halted.halted_at)

    reconciled_at = halted.halted_at + timedelta(seconds=1)
    cleared = store.clear(reconciled_at)
    restored = store.load()
    assert cleared.trading_halted is False
    assert restored.trading_halted is False
    assert restored.halt_reason is None
    assert restored.halted_at is None
    assert restored.last_reconciliation_at == reconciled_at


def test_clear_rejects_naive_reconciliation_timestamp(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("DRIFT")
    with pytest.raises(ValueError, match="timezone-aware"):
        store.clear(datetime.now())


def test_missing_state_is_fail_open_for_uninitialized_store(tmp_path):
    state = SafetyStateStore(str(tmp_path / "missing.json")).load()
    assert state == SafetyState()


def test_corrupt_state_fails_closed(tmp_path):
    path = tmp_path / "safety.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid persisted safety state"):
        SafetyStateStore(str(path)).load()


def test_blank_halt_reason_rejected(tmp_path):
    with pytest.raises(ValueError, match="halt reason"):
        SafetyStateStore(str(tmp_path / "safety.json")).halt("  ")
