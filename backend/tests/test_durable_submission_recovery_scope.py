from app.broker_submission_recovery import BrokerLookupResult, BrokerLookupStatus, SubmissionRecoveryService
from app.durable_submission_recovery import DurableSubmissionRecovery
from app.order_submission_service import BrokerSubmissionResult
from app.transactional_execution_repository import TransactionalExecutionRepository


class Adapter:
    def find_by_idempotency_key(self, intent):
        return BrokerLookupResult(BrokerLookupStatus.FOUND, BrokerSubmissionResult("broker-existing", intent.client_order_id))

    def submit_idempotent(self, intent):
        raise AssertionError("recovery must not submit when broker lookup finds the order")


def test_pending_submission_reconstructs_exact_order_intent(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.register_submission("idem-1", order_id, 1, "primary")
    outcomes = DurableSubmissionRecovery(repo, SubmissionRecoveryService(Adapter())).recover_pending()
    assert outcomes == [type(outcomes[0])("idem-1", "SUBMITTED", "broker-existing")]
    assert repo.pending_submissions() == []
    repo.close()


def test_pending_submission_scope_mismatch_is_rejected(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    repo.register_submission("idem-1", order_id, 2, "primary")
    try:
        DurableSubmissionRecovery(repo, SubmissionRecoveryService(Adapter())).recover_pending()
        raise AssertionError("scope mismatch should fail closed")
    except ValueError as exc:
        assert "scope" in str(exc)
    finally:
        repo.close()
