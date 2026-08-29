from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.broker_router import BrokerRouter, BrokerRoute
from app.broker_adapter import BrokerAdapter
from app.reconciliation import ReconciliationEngine
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


def _router(safety_store):
    adapter = Mock(spec=BrokerAdapter)
    store = SubmissionIntentStore()
    return BrokerRouter(
        routes=[BrokerRoute("upstox:account:7", adapter, broker_account_id=7, generation="route-1")],
        default_route="upstox:account:7",
        safety_store=safety_store,
        submission_intent_store=store,
        reconciliation_engine=ReconciliationEngine(store),
    )


def test_first_account_reconciliation_generation_starts_at_one(tmp_path):
    safety = Mock(spec=SafetyStateStore)
    safety.account_reconciliation.return_value = None
    router = _router(safety)

    assert router._next_reconciliation_generation(router.get()) == 1
    safety.account_reconciliation.assert_called_once_with("7")


def test_account_reconciliation_generation_increments_from_persisted_value(tmp_path):
    safety = Mock(spec=SafetyStateStore)
    safety.account_reconciliation.return_value = {"reconciliation_generation": 7}
    router = _router(safety)

    assert router._next_reconciliation_generation(router.get()) == 8


def test_invalid_persisted_reconciliation_generation_fails_closed():
    safety = Mock(spec=SafetyStateStore)
    safety.account_reconciliation.return_value = {"reconciliation_generation": "corrupt"}
    router = _router(safety)

    with pytest.raises(RuntimeError, match="generation is invalid"):
        router._next_reconciliation_generation(router.get())


def test_negative_persisted_reconciliation_generation_fails_closed():
    safety = Mock(spec=SafetyStateStore)
    safety.account_reconciliation.return_value = {"reconciliation_generation": -1}
    router = _router(safety)

    with pytest.raises(RuntimeError, match="generation is invalid"):
        router._next_reconciliation_generation(router.get())
