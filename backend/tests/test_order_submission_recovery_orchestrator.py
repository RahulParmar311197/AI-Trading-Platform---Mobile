from app.broker_submission_recovery import BrokerLookupResult, BrokerLookupStatus, SubmissionRecoveryService
from app.order_submission_recovery_orchestrator import OrderSubmissionRecoveryOrchestrator
from app.order_submission_service import BrokerSubmissionResult
from app.transactional_execution_repository import TransactionalExecutionRepository


class Adapter:
    def __init__(self, status):
        self.status = status
        self.submit_calls = 0

    def find_by_idempotency_key(self, intent):
        if self.status is BrokerLookupStatus.FOUND:
            return BrokerLookupResult(self.status, BrokerSubmissionResult("existing-1", intent.client_order_id))
        return BrokerLookupResult(self.status)

    def submit_idempotent(self, intent):
        self.submit_calls += 1
        return BrokerSubmissionResult("new-1", intent.client_order_id)


def setup(tmp_path, status):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.register_submission("idem-1", order, 1, "primary")
    recovery = SubmissionRecoveryService(Adapter(status))
    return repo, recovery


def test_found_marks_pending_submitted(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.FOUND)
    result = OrderSubmissionRecoveryOrchestrator(repo, recovery).recover_pending()
    assert result[0].status == "SUBMITTED"
    assert result[0].broker_order_id == "existing-1"
    assert repo.pending_submissions() == []
    repo.close()


def test_not_found_uses_idempotent_submit(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.NOT_FOUND)
    result = OrderSubmissionRecoveryOrchestrator(repo, recovery).recover_pending()
    assert result[0].status == "SUBMITTED"
    assert repo.pending_submissions() == []
    repo.close()


def test_ambiguous_stays_pending_and_is_quarantined(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.AMBIGUOUS)
    result = OrderSubmissionRecoveryOrchestrator(repo, recovery).recover_pending()
    assert result[0].status == "QUARANTINED"
    assert repo.pending_submissions()[0].status == "PENDING"
    repo.close()
