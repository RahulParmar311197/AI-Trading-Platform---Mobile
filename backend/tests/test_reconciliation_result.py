from datetime import datetime, timedelta, timezone

import pytest

from app.reconciliation import ReconciliationEngine
from app.reconciliation_result import ReconciliationResult


def _valid_check():
    engine = ReconciliationEngine()
    return engine.check([], [], [], [])


def _valid(**overrides):
    values = {
        "account_id": "acct-1",
        "generation": 3,
        "reconciled_at": datetime.now(timezone.utc),
        "open_orders_reconciled": True,
        "positions_reconciled": True,
        "submission_intents_resolved": 0,
        "broker_ready": True,
        "broker_snapshot_fingerprint": "fp-1",
    }
    values.update(overrides)
    return ReconciliationEngine().build_verified_result(_valid_check(), **values)


def test_verified_reconciliation_requires_authenticated_engine_check():
    result = _valid()
    assert result.verified is True


@pytest.mark.parametrize("field", ["open_orders_reconciled", "positions_reconciled", "broker_ready"])
def test_unreconciled_or_unready_state_cannot_unlock(field):
    with pytest.raises(ValueError):
        _valid(**{field: False})


def test_future_reconciliation_is_rejected():
    with pytest.raises(ValueError, match="future"):
        _valid(reconciled_at=datetime.now(timezone.utc) + timedelta(minutes=1))


def test_naive_reconciliation_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        _valid(reconciled_at=datetime.now())


def test_negative_submission_intents_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        _valid(submission_intents_resolved=-1)


def test_direct_construction_is_not_allowed():
    with pytest.raises(TypeError, match="verified factory"):
        ReconciliationResult(
            account_id="acct-1",
            generation=1,
            reconciled_at=datetime.now(timezone.utc),
            open_orders_reconciled=True,
            positions_reconciled=True,
            submission_intents_resolved=0,
            broker_ready=True,
            broker_snapshot_fingerprint="fp-1",
        )


def test_old_unbound_factory_is_removed():
    assert not hasattr(ReconciliationResult, "from_verified_state")
