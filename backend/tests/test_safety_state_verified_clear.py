from datetime import datetime, timedelta, timezone

import pytest

from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyStateStore


def _result(at=None):
    return ReconciliationResult(
        account_id="acct-1",
        generation=7,
        reconciled_at=at or datetime.now(timezone.utc),
        open_orders_reconciled=True,
        positions_reconciled=True,
        submission_intents_resolved=0,
        broker_ready=True,
    )


def test_halt_clear_requires_verified_result(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("broker disconnect")
    with pytest.raises(ValueError, match="verified reconciliation"):
        store.clear(None)


def test_halt_clear_persists_reconciliation_identity(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    halted = store.halt("manual safety halt")
    result = _result(halted.halted_at + timedelta(seconds=1))
    cleared = store.clear(result)
    assert cleared.trading_halted is False
    assert cleared.reconciliation_generation == 7
    assert cleared.reconciliation_account_id == "acct-1"
    restored = store.load()
    assert restored.reconciliation_generation == 7
    assert restored.reconciliation_account_id == "acct-1"


def test_stale_verified_result_cannot_clear_halt(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    halted = store.halt("halt")
    result = _result(halted.halted_at)
    with pytest.raises(RuntimeError, match="after the safety halt"):
        store.clear(result)
