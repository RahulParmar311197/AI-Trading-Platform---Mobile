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


class FakeLookup:
    def __init__(self, matches=None, error=None):
        self.calls = 0
        self.matches = matches or []
        self.error = error

    def lookup(self, client_order_id, broker_account_id, broker_route):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.matches)


def make_service(tmp_path, broker, lookup=None):
    repository = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order_id = repository.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    intent = OrderIntent(order_id, "NIFTY", "BUY", 5, 1, "primary", f"idem-{order_id}")
    return repository, OrderSubmissionService(repository, broker, lookup=lookup), intent


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


def test_pending_submission_is_resolved_from_exactly_one_broker_match(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    lookup = FakeLookup([BrokerSubmissionResult("broker-42", "pending-client")])
    repository, service, intent = make_service(tmp_path, broker, lookup)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    lookup.matches = [BrokerSubmissionResult("broker-42", intent.client_order_id)]
    resolved = service.reconcile_pending()
    assert resolved == [BrokerSubmissionResult("broker-42", intent.client_order_id)]
    assert lookup.calls == 1
    assert broker.calls == 1
    assert repository.get_submission(intent.idempotency_key).status == "SUBMITTED"
    assert repository.get_submission(intent.idempotency_key).broker_order_id == "broker-42"


def test_no_broker_match_stays_pending_and_never_submits_again(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    lookup = FakeLookup([])
    repository, service, intent = make_service(tmp_path, broker, lookup)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    assert service.reconcile_pending() == []
    assert service.reconcile_pending() == []
    assert broker.calls == 1
    assert lookup.calls == 2
    assert repository.get_submission(intent.idempotency_key).status == "PENDING"


def test_lookup_failure_keeps_submission_pending(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    lookup = FakeLookup(error=ConnectionError("broker unavailable"))
    repository, service, intent = make_service(tmp_path, broker, lookup)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    with pytest.raises(AmbiguousBrokerSubmission, match="lookup unavailable"):
        service.reconcile_pending()
    assert repository.get_submission(intent.idempotency_key).status == "PENDING"
    assert broker.calls == 1


def test_multiple_broker_matches_fail_closed(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    lookup = FakeLookup([
        BrokerSubmissionResult("broker-1", "client"),
        BrokerSubmissionResult("broker-2", "client"),
    ])
    repository, service, intent = make_service(tmp_path, broker, lookup)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    with pytest.raises(AmbiguousBrokerSubmission, match="multiple broker orders"):
        service.reconcile_pending()
    assert repository.get_submission(intent.idempotency_key).status == "PENDING"


def test_lookup_identity_mismatch_fails_closed(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    lookup = FakeLookup([BrokerSubmissionResult("broker-1", "different-client")])
    repository, service, intent = make_service(tmp_path, broker, lookup)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    with pytest.raises(AmbiguousBrokerSubmission, match="identity mismatch"):
        service.reconcile_pending()
    assert repository.get_submission(intent.idempotency_key).status == "PENDING"


def test_missing_lookup_is_fail_closed(tmp_path):
    broker = FakeBroker(error=TimeoutError("request timed out"))
    repository, service, intent = make_service(tmp_path, broker)
    with pytest.raises(AmbiguousBrokerSubmission):
        service.submit(intent)
    with pytest.raises(AmbiguousBrokerSubmission, match="broker lookup is required"):
        service.reconcile_pending()
    assert repository.get_submission(intent.idempotency_key).status == "PENDING"


def test_missing_idempotency_key_is_rejected(tmp_path):
    broker = FakeBroker()
    repository, service, intent = make_service(tmp_path, broker)
    invalid = OrderIntent(intent.client_order_id, intent.symbol, intent.side, intent.quantity, intent.broker_account_id, intent.broker_route, "")
    with pytest.raises(ValueError, match="idempotency key"):
        service.submit(invalid)
    assert broker.calls == 0
