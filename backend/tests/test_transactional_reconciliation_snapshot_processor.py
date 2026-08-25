from datetime import datetime, timezone

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_reconciliation_snapshot_processor import TransactionalReconciliationSnapshotProcessor


def test_snapshot_processor_binds_and_quarantines_on_single_db(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    quarantine = ExecutionEventQuarantine(db)
    processor = TransactionalReconciliationSnapshotProcessor(repo, quarantine)
    now = datetime.now(timezone.utc)
    result = processor.process("upstox", [BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now)], [InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)])
    assert result.matched == 1
    assert repo.get_identity_by_broker("upstox", "b1").client_order_id == "client-1"
    assert quarantine.pending() == []
    quarantine.close(); repo.close()
