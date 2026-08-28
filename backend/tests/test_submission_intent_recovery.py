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

    def get_order_snapshot(self):
        from app.broker_order_snapshot import BrokerOrderSnapshot
        return BrokerOrderSnapshot(orders=[dict(o) for o in self.orders], complete=True, source="test")


def _router(tmp_path, orders):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    adapter = Adapter(orders)
    router = BrokerRouter(
        [BrokerRoute("live", adapter, broker_account_id=11, generation="4")],
        "live",
        submission_intent_store=store,
    )
    return router, store


def _create_intent(store, client_id="cid-1"):
    store.create(client_order_id=client_id, route="live", account_id="11", symbol="NIFTY", side="BUY", quantity=1, request_fingerprint="fp")


def test_startup_recovery_resolves_found_intent_without_resubmission(tmp_path):
    router, store = _router(tmp_path, [{"client_order_id": "cid-1", "order_id": "br-1", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 1}])
    _create_intent(store)

    resolved = router.reconcile_unresolved_submission_intents()

    assert resolved == ["cid-1"]
    assert router.unresolved_submission_intent_count() == 0


def test_startup_recovery_keeps_missing_intent_unresolved_and_halts(tmp_path):
    router, store = _router(tmp_path, [])
    _create_intent(store, "cid-2")

    resolved = router.reconcile_unresolved_submission_intents()

    assert resolved == []
    assert router.unresolved_submission_intent_count() == 1


def test_startup_recovery_halts_on_ambiguous_intent(tmp_path):
    router, store = _router(tmp_path, [
        {"client_order_id": "cid-3", "order_id": "br-1", "symbol": "NIFTY", "side": "BUY", "quantity": 1},
        {"client_order_id": "cid-3", "order_id": "br-2", "symbol": "NIFTY", "side": "BUY", "quantity": 1},
    ])
    _create_intent(store, "cid-3")

    with pytest.raises(RuntimeError, match="ambiguous"):
        router.reconcile_unresolved_submission_intents()

    assert router.unresolved_submission_intent_count() == 1


def test_startup_recovery_rejects_payload_mismatch(tmp_path):
    router, store = _router(tmp_path, [{
        "client_order_id": "cid-4",
        "order_id": "br-4",
        "status": "NEW",
        "symbol": "BANKNIFTY",
        "side": "BUY",
        "quantity": 1,
    }])
    _create_intent(store, "cid-4")

    with pytest.raises(RuntimeError, match="payload mismatch"):
        router.reconcile_unresolved_submission_intents()

    assert router.unresolved_submission_intent_count() == 1


def test_startup_recovery_rejects_quantity_mismatch(tmp_path):
    router, store = _router(tmp_path, [{
        "client_order_id": "cid-5",
        "order_id": "br-5",
        "status": "NEW",
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 2,
    }])
    _create_intent(store, "cid-5")

    with pytest.raises(RuntimeError, match="payload mismatch"):
        router.reconcile_unresolved_submission_intents()

    assert router.unresolved_submission_intent_count() == 1
