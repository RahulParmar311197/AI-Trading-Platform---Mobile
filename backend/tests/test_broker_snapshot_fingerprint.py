from datetime import timedelta

import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyStateStore


def _router(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    adapter = PaperBrokerAdapter()
    router = BrokerRouter(
        [BrokerRoute("live", adapter, broker_account_id=7, generation="g1")],
        "live",
        safety_store=store,
    )
    return router, adapter, store


def _reconcile_store(router, store):
    snapshot = router.get_snapshot("live")
    halted = store.halt("reconcile")
    result = ReconciliationResult.from_verified_state(
        account_id="7",
        generation=1,
        reconciled_at=halted.halted_at + timedelta(seconds=1),
        open_orders_reconciled=True,
        positions_reconciled=True,
        submission_intents_resolved=0,
        broker_ready=True,
        broker_snapshot_fingerprint=snapshot.fingerprint(),
    )
    store.clear(result)


def test_unchanged_broker_snapshot_allows_submission(tmp_path):
    router, _, store = _router(tmp_path)
    _reconcile_store(router, store)
    order = router.submit(BrokerOrderRequest("c1", "NIFTY", "BUY", 1, broker_route="live"))
    assert order.order_id


def test_changed_broker_snapshot_blocks_submission(tmp_path):
    router, adapter, store = _router(tmp_path)
    _reconcile_store(router, store)
    adapter._orders["external"] = {
        "order_id": "external",
        "broker_order_id": "external",
        "client_order_id": "manual-1",
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 1,
        "filled_quantity": 0,
        "status": "NEW",
    }
    with pytest.raises(RuntimeError, match="broker state changed since reconciliation"):
        router.submit(BrokerOrderRequest("c2", "NIFTY", "BUY", 1, broker_route="live"))
