from datetime import datetime, timezone
import pytest

from app.broker_execution_context import BrokerExecutionContext
from app.reconciliation import ReconciliationEngine
from app.submission_intent_store import SubmissionIntentStore


def context(observed_at: str) -> BrokerExecutionContext:
    return BrokerExecutionContext(account_id="acct", broker_route="paper", route_generation="g1", generation=1, snapshot_fingerprint="fp", observed_at=datetime.fromisoformat(observed_at))


def build(engine):
    checked = engine.check([], [], [], [])
    return engine.build_verified_result(checked, context=context(checked.checked_at), reconciled_at=datetime.now(timezone.utc), open_orders_reconciled=True, positions_reconciled=True, submission_intents_resolved=0, broker_ready=True)


def test_verified_result_requires_durable_submission_intent_store():
    engine = ReconciliationEngine()
    with pytest.raises(ValueError, match="durable submission intent store"):
        build(engine)


def test_verified_result_rejects_unresolved_submission_intents(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    store.create(client_order_id="c1", route="paper", account_id="acct", symbol="NIFTY", side="BUY", quantity=1, request_fingerprint="r1")
    engine = ReconciliationEngine(store)
    with pytest.raises(ValueError, match="unresolved submission intent"):
        build(engine)


def test_verified_result_allows_zero_unresolved_intents(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    engine = ReconciliationEngine(store)
    result = build(engine)
    assert result.verified
    assert result.submission_intents_resolved == 0
