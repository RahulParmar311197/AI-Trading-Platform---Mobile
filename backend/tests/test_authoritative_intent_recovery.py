from pathlib import Path
from types import SimpleNamespace

import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_router import BrokerRoute, BrokerRouter
from app.submission_intent_store import SubmissionIntentStore


class IncompleteAdapter(PaperBrokerAdapter):
    def get_order_snapshot(self):
        return BrokerOrderSnapshot(orders=[], complete=False, source="test")


def _router(tmp_path: Path, adapter):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    store.create(
        client_order_id="cid-1",
        route="paper",
        account_id="1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp",
    )
    safety = SimpleNamespace(halt=lambda reason: setattr(safety, "reason", reason))
    router = BrokerRouter(
        routes=[BrokerRoute("paper", adapter, broker_account_id=1, generation="1")],
        default_route="paper",
        submission_intent_store=store,
        safety_store=safety,
    )
    return router, store, safety


def test_incomplete_snapshot_does_not_resolve_intent(tmp_path):
    router, store, safety = _router(tmp_path, IncompleteAdapter())
    with pytest.raises(RuntimeError, match="not authoritative"):
        router.reconcile_unresolved_submission_intents()
    assert store.unresolved_count() == 1
    assert "snapshot" in safety.reason


def test_paper_snapshot_is_authoritative():
    snapshot = PaperBrokerAdapter().get_order_snapshot()
    assert snapshot.complete is True
    assert snapshot.require_authoritative() == []
