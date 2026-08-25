from app.broker_submission_recovery import BrokerLookupResult, BrokerLookupStatus, SubmissionRecoveryService
from app.durable_submission_recovery import DurableSubmissionRecovery
from app.order_submission_service import BrokerSubmissionResult
from app.transactional_execution_repository import TransactionalExecutionRepository


class Adapter:
    def __init__(self, status):
        self.status = status
        self.submits = 0

    def find_by_idempotency_key(self, intent):
        if self.status == BrokerLookupStatus.FOUND:
            return BrokerLookupResult(self.status, BrokerSubmissionResult("broker-existing", intent.client_order_id))
        return BrokerLookupResult(self.status)

    def submit_idempotent(self, intent):
        self.submits += 1
        return BrokerSubmissionResult("broker-new", intent.client_order_id)


def setup(tmp_path, status):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    repo.register_submission("idem-1", "client-1", "NIFTY", "BUY", 5, 1, "primary")
    recovery = SubmissionRecoveryService(Adapter(status))
    return repo, recovery


def test_pending_found_is_bound_without_new_submit(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.FOUND)
    outcomes = DurableSubmissionRecovery(repo, recovery).recover_pending()
    assert outcomes[0].status == "SUBMITTED"
    assert outcomes[0].broker_order_id == "broker-existing"
    assert repo.pending_submissions() == []
    repo.close()


def test_pending_not_found_uses_idempotent_submit(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.NOT_FOUND)
    outcomes = DurableSubmissionRecovery(repo, recovery).recover_pending()
    assert outcomes[0].status == "SUBMITTED"
    assert repo.pending_submissions() == []
    repo.close()


def test_pending_ambiguous_is_quarantined_without_submit(tmp_path):
    repo, recovery = setup(tmp_path, BrokerLookupStatus.AMBIGUOUS)
    outcomes = DurableSubmissionRecovery(repo, recovery).recover_pending()
    assert outcomes[0].status == "QUARANTINED"
    assert repo.pending_submissions()[0]["status"] == "PENDING"
    repo.close()
