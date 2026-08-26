import pytest

from app.order_submission_service import (
    AmbiguousBrokerSubmission,
    BrokerSubmissionResult,
    OrderIntent,
    OrderSubmissionService,
)
from app.transactional_execution_repository import TransactionalExecutionRepository


class FakeBroker:
    def __init__(self, result=None, error=None):
        self.calls = 0
        self.result = result
        self.error = error

    def submit(self, intent):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result or BrokerSubmissionResult(f"broker-{self.calls}", intent.client_order_id)


def make_service(tmp_path, broker):
    repository = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repository.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    intent = OrderIntent(order_id, "NIFTY", "BUY", 5, 1, "primary", f"idem-{order_id}")
    return repository, OrderSubmissionService(repository, broker), intent


def test_safe_order_reaches_broker_once(tmp_path):
    broker = FakeBroker()
    repository, service, intent = make_service(tmp_path, broker)
    first = service.submit(intent)
    second = service.submit(intent)
    assert first == second
    assert broker.calls == 1
    assert repository.get_submission(intent.idempotency_key).status == "SUBMITTED"


@pytest.mark.parametrize("kwargs", [
    {"emergency_halt": True},
    {"reconciliation_ready": False},
    {"broker_healthy": False},
    {"risk_allowed": False},
])
def test_safety_failure_prevents_broker_submission(tmp_path, kwargs):
    broker = FakeBroker()
    repository, service, intent = make_service(tmp_path, broker)
    with pytest.raises(PermissionError):
        service.submit(intent, **kwargs)
    assert broker.calls == 0


def test_broker_exception_is_ambiguous_and_remains_pending(tmp_path):
    broker = FakeBroker(error=TimeoutError("broker request timed out"))
    repository, service, intent = make_service(tmp_path, broker)
    with pytest.raises(AmbiguousBrokerSubmission, match="outcome is unknown"):
        service.submit(intent)
    record = repository.get_submission(intent.idempotency_key)
    assert broker.calls == 1
    assert record.status == "PENDING"
    assert record.broker_order_id is None
    with pytest.raises(AmbiguousBrokerSubmission, match="manual broker reconciliation"):
        service.recover_pending()


def test_invalid_broker_response_is_ambiguous_and_not_marked_submitted(tmp_path):
    broker = FakeBroker(result=BrokerSubmissionResult("", "wrong-client"))
    repository, service, intent = make_service(tmp_path, broker)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    record = repository.get_submission(intent.idempotency_key)
    assert record.status == "PENDING"
    assert record.broker_order_id is None


def test_missing_idempotency_key_is_rejected(tmp_path):
    broker = FakeBroker()
    repository, service, intent = make_service(tmp_path, broker)
    invalid = OrderIntent(intent.client_order_id, intent.symbol, intent.side, intent.quantity, intent.broker_account_id, intent.broker_route, "")
    with pytest.raises(ValueError, match="idempotency key"):
        service.submit(invalid)
    assert broker.calls == 0
