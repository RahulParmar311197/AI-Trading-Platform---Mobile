from datetime import datetime, timezone

from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_reconciliation_service import TransactionalReconciliationService


def test_reconciliation_identity_uses_single_repository(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    service = TransactionalReconciliationService(repo)
    now = datetime.now(timezone.utc)
    result = service.bind_deterministic("upstox", BrokerOrderSnapshot("b1", "NIFTY", "BUY", 5, now), [InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)])
    assert result is not None
    assert repo.get_identity_by_broker("upstox", "b1").client_order_id == "client-1"
    repo.close()
