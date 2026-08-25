from datetime import datetime, timezone
import pytest

from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_reconciliation_snapshot_processor import TransactionalReconciliationSnapshotProcessor
from app.execution_event_quarantine import ExecutionEventQuarantine


def test_snapshot_scope_must_match_candidate_order(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    quarantine = ExecutionEventQuarantine(db)
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=7, broker_route="primary")
    processor = TransactionalReconciliationSnapshotProcessor(repo, quarantine)
    now = datetime.now(timezone.utc)
    candidate = InternalOrderCandidate(order_id, "NIFTY", "BUY", 5, now, broker_account_id=8, broker_route="primary")
    with pytest.raises(ValueError, match="broker account"):
        processor.process("upstox", [BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now, broker_account_id=8, broker_route="primary")], [candidate])
    assert repo.get_identity_by_broker("upstox", "b1", broker_account_id=7, broker_route="primary") is None
    quarantine.close(); repo.close()
