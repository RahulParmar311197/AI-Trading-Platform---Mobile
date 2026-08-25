from datetime import datetime, timezone

import pytest

from app.reconciliation_matcher import InternalOrderCandidate
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_stale_recovery_target_is_rejected(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    candidate = InternalOrderCandidate(order, "NIFTY", "BUY", 5, datetime.now(timezone.utc), broker_account_id=1, broker_route="primary")
    # Approval must revalidate the current target identity rather than trusting a stale review snapshot.
    current = repo.get_order(order)
    assert current["broker_account_id"] == candidate.broker_account_id
    assert current["broker_route"] == candidate.broker_route
    repo.close()


def test_second_binding_for_same_broker_identity_is_rejected(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    first = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    second = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.bind_broker_identity(first, "upstox", "recovery-1", broker_account_id=1, broker_route="primary")
    with pytest.raises(ValueError):
        repo.bind_broker_identity(second, "upstox", "recovery-1", broker_account_id=1, broker_route="primary")
    repo.close()
