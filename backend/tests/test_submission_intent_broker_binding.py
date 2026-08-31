import json
from datetime import datetime, timedelta

import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_execution_context import BrokerExecutionContext
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


def _ready_router(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    intents = SubmissionIntentStore(str(tmp_path / "intents.json"))
    router = BrokerRouter(
        [BrokerRoute("paper", PaperBrokerAdapter())],
        "paper",
        safety_store=safety,
        submission_intent_store=intents,
    )
    check = router.reconciliation_engine.check([], [], [], [])
    observed = datetime.fromisoformat(check.checked_at)
    fingerprint = router._current_snapshot_fingerprint(router.get("paper"))
    context = BrokerExecutionContext(
        account_id="paper",
        broker_route="paper",
        route_generation="paper-1",
        generation=1,
        snapshot_fingerprint=fingerprint,
        observed_at=observed,
    )
    halted = safety.halt("test reconciliation")
    reconciled_at = max(halted.halted_at + timedelta(milliseconds=1), observed)
    result = router.reconciliation_engine.build_verified_result(
        check,
        context=context,
        reconciled_at=reconciled_at,
        open_orders_reconciled=True,
        positions_reconciled=True,
        submission_intents_resolved=0,
        broker_ready=True,
    )
    safety.clear(result, active_context=result.context)
    return router, intents


def test_successful_submission_binds_broker_order_before_resolving_intent(tmp_path):
    router, intents = _ready_router(tmp_path)
    result = router.submit(BrokerOrderRequest("client-1", "NIFTY", "BUY", 1))

    assert result.order_id
    assert intents.unresolved_count() == 0
    persisted = json.loads((tmp_path / "intents.json").read_text(encoding="utf-8"))["client-1"]
    assert persisted["broker_order_id"] == result.order_id
    assert persisted["broker_status"] == result.status.value
    assert persisted["resolved_at"] is not None
    assert persisted["recovered_at"] is not None


class TimeoutAfterAcceptanceBroker(PaperBrokerAdapter):
    def submit_order(self, order):
        result = super().submit_order(order)
        raise RuntimeError("transport lost after broker acceptance")


def test_ambiguous_submission_recovery_binds_broker_order_before_resolving(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    intents = SubmissionIntentStore(str(tmp_path / "intents.json"))
    broker = TimeoutAfterAcceptanceBroker()
    router = BrokerRouter([BrokerRoute("paper", broker)], "paper", safety_store=safety, submission_intent_store=intents)
    check = router.reconciliation_engine.check([], [], [], [])
    observed = datetime.fromisoformat(check.checked_at)
    fingerprint = router._current_snapshot_fingerprint(router.get("paper"))
    context = BrokerExecutionContext(
        account_id="paper", broker_route="paper", route_generation="paper-1",
        generation=1, snapshot_fingerprint=fingerprint, observed_at=observed,
    )
    halted = safety.halt("test reconciliation")
    result = router.reconciliation_engine.build_verified_result(
        check, context=context,
        reconciled_at=max(halted.halted_at + timedelta(milliseconds=1), observed),
        open_orders_reconciled=True, positions_reconciled=True,
        submission_intents_resolved=0, broker_ready=True,
    )
    safety.clear(result, active_context=result.context)

    recovered = router.submit(BrokerOrderRequest("client-recovered", "NIFTY", "BUY", 1))

    assert recovered.order_id
    assert recovered.message == "BROKER_SUBMISSION_RECOVERED"
    assert intents.unresolved_count() == 0
    persisted = json.loads((tmp_path / "intents.json").read_text(encoding="utf-8"))["client-recovered"]
    assert persisted["broker_order_id"] == recovered.order_id
    assert persisted["broker_status"] == recovered.status.value
    assert persisted["resolved_at"] is not None
