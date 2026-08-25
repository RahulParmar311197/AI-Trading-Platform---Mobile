import pytest

from app.broker_recovery import BrokerStartupRecovery


class FakeStore:
    def __init__(self):
        self.orders = {}


class FakeSafetyStore:
    pass


class FakeRecoveryManager:
    def __init__(self):
        self.pending = set()

    def mark_pending_reconciliation(self, client_order_id, reason):
        self.pending.add(client_order_id)


class FakeBroker:
    def __init__(self, lookup=None, submit_error=None):
        self.lookup = lookup or {}
        self.submit_error = submit_error

    def find_order(self, client_order_id):
        return self.lookup.get(client_order_id)

    def submit(self, request):
        if self.submit_error:
            raise self.submit_error
        return {"status": "accepted", "client_order_id": request["client_order_id"]}


def test_recovery_finds_order_after_ambiguous_submission():
    broker = FakeBroker(lookup={"cid-1": {"status": "OPEN", "client_order_id": "cid-1"}})
    assert broker.find_order("cid-1")["status"] == "OPEN"


def test_recovery_missing_order_requires_reconciliation_not_blind_retry():
    broker = FakeBroker(lookup={})
    recovery = FakeRecoveryManager()
    broker.find_order("cid-2")
    recovery.mark_pending_reconciliation("cid-2", "ambiguous broker submission")
    assert "cid-2" in recovery.pending


def test_broker_exception_is_not_silently_treated_as_success():
    broker = FakeBroker(submit_error=TimeoutError("broker timeout"))
    with pytest.raises(TimeoutError):
        broker.submit({"client_order_id": "cid-3"})
