from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_router import BrokerRoute, BrokerRouter
from app.submission_intent_store import SubmissionIntentStore


class SnapshotAdapter(BrokerAdapter):
    def __init__(self, orders):
        self.orders = orders

    def submit_order(self, order):
        raise AssertionError("submit_order must not be called during reconciliation")

    def cancel_order(self, broker_order_id):
        raise NotImplementedError

    def get_order(self, broker_order_id):
        raise NotImplementedError

    def get_positions(self):
        return []

    def get_account(self):
        return {}

    def get_order_snapshot(self):
        return BrokerOrderSnapshot(orders=[dict(o) for o in self.orders], complete=True, source="test")


def make_intent(store):
    return store.create(
        client_order_id="c1",
        route="test",
        account_id=None,
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp",
    )


def test_zero_match_authoritative_snapshot_does_not_resolve_intent(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    make_intent(store)
    router = BrokerRouter(
        routes=[BrokerRoute(name="test", adapter=SnapshotAdapter([]))],
        default_route="test",
        submission_intent_store=store,
    )

    assert router.reconcile_unresolved_submission_intents() == []
    assert store.unresolved_count() == 1


def test_single_match_authoritative_snapshot_resolves_intent(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    make_intent(store)
    router = BrokerRouter(
        routes=[BrokerRoute(name="test", adapter=SnapshotAdapter([{"order_id": "o1", "client_order_id": "c1"}]))],
        default_route="test",
        submission_intent_store=store,
    )

    assert router.reconcile_unresolved_submission_intents() == ["c1"]
    assert store.unresolved_count() == 0
