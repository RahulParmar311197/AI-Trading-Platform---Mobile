from types import SimpleNamespace

import pytest

from app.broker_router import BrokerRoute, BrokerRouter
from app.submission_intent_store import SubmissionIntentStore


class Adapter:
    def __init__(self, orders):
        self.orders = orders

    def get_orders(self):
        return list(self.orders)

    def get_positions(self):
        return []

    def get_account(self):
        return {"healthy": True, "authenticated": True}


def _router(tmp_path, orders):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    adapter = Adapter(orders)
    router = BrokerRouter(
        [BrokerRoute("live", adapter, broker_account_id=11, generation="4")],
        "live",
        submission_intent_store=store,
    )
    return router, store


def test_startup_recovery_resolves_found_intent_without_resubmission(tmp_path):
    router, store = _router(tmp_path, [{"client_order_id": "cid-1", "order_id": "br-1", "status": "NEW"}])
    store.create(client_order_id="cid-1", route="live", account_id="11", symbol="NIFTY", side="BUY", quantity=1, request_fingerprint="fp")

    resolved = router.reconcile_unresolved_submission_intents()

    assert resolved == ["cid-1"]
    assert router.unresolved_submission_intent_count() == 0


def test_startup_recovery_does_not_resubmit_missing_intent(tmp_path):
    router, store = _router(tmp_path, [])
    store.create(client_order_id="cid-2", route="live", account_id="11", symbol="NIFTY", side="BUY", quantity=1, request_fingerprint="fp")

    resolved = router.reconcile_unresolved_submission_intents()

    assert resolved == ["cid-2"]
    assert router.unresolved_submission_intent_count() == 0


def test_startup_recovery_halts_on_ambiguous_intent(tmp_path):
    router, store = _router(tmp_path, [
        {"client_order_id": "cid-3", "order_id": "br-1"},
        {"client_order_id": "cid-3", "order_id": "br-2"},
    ])
    store.create(client_order_id="cid-3", route="live", account_id="11", symbol="NIFTY", side="BUY", quantity=1, request_fingerprint="fp")

    with pytest.raises(RuntimeError, match="ambiguous"):
        router.reconcile_unresolved_submission_intents()

    assert router.unresolved_submission_intent_count() == 1
