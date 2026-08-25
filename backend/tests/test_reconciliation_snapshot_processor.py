from datetime import datetime, timezone

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentityRegistry
from app.reconciliation_event_recovery import ReconciliationEventRecovery
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate
from app.reconciliation_snapshot_processor import ReconciliationSnapshotProcessor
from app.transactional_execution_repository import TransactionalExecutionRepository


def test_snapshot_binds_deterministic_match_and_quarantines_ambiguity(tmp_path):
    db = str(tmp_path / "execution.db")
    repo = TransactionalExecutionRepository(db)
    order_id = repo.create_order("NIFTY", "BUY", 5)
    registry = OrderIdentityRegistry(db)
    quarantine = ExecutionEventQuarantine(db)
    recovery = ReconciliationEventRecovery(registry, quarantine, repo)
    processor = ReconciliationSnapshotProcessor(registry, quarantine, recovery)
    now = datetime.now(timezone.utc)
    result = processor.process(
        [BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now)],
        [InternalOrderCandidate(order_id, "NIFTY", "BUY", 5, now)],
    )
    assert result.matched == 1
    assert registry.by_broker("reconciliation", "b1").client_order_id == order_id
    repo.close(); quarantine.close(); registry.close()
