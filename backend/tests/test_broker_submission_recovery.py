import pytest

from app.broker_submission_recovery import BrokerLookupResult, BrokerLookupStatus, SubmissionRecoveryService
from app.order_submission_service import BrokerSubmissionResult, OrderIntent


class Adapter:
    def __init__(self, status):
        self.status = status
        self.submit_calls = 0

    def find_by_idempotency_key(self, intent):
        if self.status is BrokerLookupStatus.FOUND:
            return BrokerLookupResult(self.status, BrokerSubmissionResult("broker-existing", intent.client_order_id))
        return BrokerLookupResult(self.status)

    def submit_idempotent(self, intent):
        self.submit_calls += 1
        return BrokerSubmissionResult("broker-new", intent.client_order_id)


def make_intent():
    return OrderIntent("client-1", "NIFTY", "BUY", 5, 1, "primary", "idem-1")


def test_found_submission_is_reused_without_new_submit():
    adapter = Adapter(BrokerLookupStatus.FOUND)
    result = SubmissionRecoveryService(adapter).recover(make_intent())
    assert result.broker_order_id == "broker-existing"
    assert adapter.submit_calls == 0


def test_not_found_uses_broker_idempotent_submit():
    adapter = Adapter(BrokerLookupStatus.NOT_FOUND)
    result = SubmissionRecoveryService(adapter).recover(make_intent())
    assert result.broker_order_id == "broker-new"
    assert adapter.submit_calls == 1


def test_ambiguous_submission_fails_closed():
    adapter = Adapter(BrokerLookupStatus.AMBIGUOUS)
    with pytest.raises(RuntimeError, match="ambiguous"):
        SubmissionRecoveryService(adapter).recover(make_intent())
    assert adapter.submit_calls == 0
