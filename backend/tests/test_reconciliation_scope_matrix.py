from datetime import datetime, timezone

import pytest

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate, ReconciliationMatcher
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository
from app.transactional_reconciliation_snapshot_processor import TransactionalReconciliationSnapshotProcessor


def _candidate(order_id, account, route):
    return InternalOrderCandidate(order_id, "NIFTY", "BUY", 5, datetime.now(timezone.utc), broker_account_id=account, broker_route=route)


def _snapshot(account, route, broker_order="same-broker-id"):
    return BrokerOrderSnapshot(broker_order, "NIFTY", "BUY", 5, datetime.now(timezone.utc), broker_account_id=account, broker_route=route)


def test_same_broker_order_id_isolated_by_account_and_route():
    a = _candidate("a", 1, "primary")
    b = _candidate("b", 2, "primary")
    c = _candidate("c", 1, "secondary")
    assert ReconciliationMatcher.match(_snapshot(1, "primary"), [a, b, c]).client_order_id == "a"
    assert ReconciliationMatcher.match(_snapshot(2, "primary"), [a, b, c]).client_order_id == "b"
    assert ReconciliationMatcher.match(_snapshot(1, "secondary"), [a, b, c]).client_order_id == "c"


def test_repository_rejects_cross_account_rebind(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    with pytest.raises(ValueError, match="mismatch"):
        repo.bind_identity(OrderIdentity(order, "upstox", "same", broker_account_id=2, broker_route="primary"))
    repo.close()


def test_snapshot_scope_isolation_does_not_bind_other_account(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    quarantine = ExecutionEventQuarantine(db)
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    processor = TransactionalReconciliationSnapshotProcessor(repo, quarantine)
    result = processor.process("upstox", [_snapshot(2, "primary")], [_candidate(order, 1, "primary")])
    assert result.matched == 0
    assert repo.get_identity_by_broker("upstox", "same-broker-id", broker_account_id=1, broker_route="primary") is None
    assert len(quarantine.pending()) == 1
    quarantine.close(); repo.close()
