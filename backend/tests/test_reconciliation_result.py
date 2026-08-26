from datetime import datetime, timedelta, timezone

import pytest

from app.reconciliation_result import ReconciliationResult


def _valid(**overrides):
    values = {
        "account_id": "acct-1",
        "generation": 3,
        "reconciled_at": datetime.now(timezone.utc),
        "open_orders_reconciled": True,
        "positions_reconciled": True,
        "submission_intents_resolved": 0,
        "broker_ready": True,
    }
    values.update(overrides)
    return ReconciliationResult(**values)


def test_verified_reconciliation_requires_all_broker_state_domains():
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
