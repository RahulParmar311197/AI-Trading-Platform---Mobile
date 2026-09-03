from __future__ import annotations

import pytest

from app.submission_intent_store import SubmissionIntentStore


def test_file_store_rejects_unknown_broker_status_before_mutation(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    store.create(
        client_order_id="client-status-1",
        route="route-1",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-1",
    )

    with pytest.raises(ValueError, match="unsupported broker status"):
        store.record_broker_order("client-status-1", "broker-1", "UNKNOWN")

    intent = store.get_unresolved("client-status-1")
    assert intent is not None
    assert intent.broker_order_id is None
    assert intent.broker_status is None
    assert intent.resolved_at is None


def test_file_store_normalizes_supported_broker_status(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    store.create(
        client_order_id="client-status-2",
        route="route-1",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-2",
    )

    store.record_broker_order("client-status-2", "broker-2", " filled ")
    intent = store.get_unresolved("client-status-2")
    assert intent is not None
    assert intent.broker_order_id == "broker-2"
    assert intent.broker_status == "FILLED"


def test_empty_broker_status_is_rejected_before_binding(tmp_path):
    store = SubmissionIntentStore(tmp_path / "intents.json")
    store.create(
        client_order_id="client-status-3",
        route="route-1",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-3",
    )

    with pytest.raises(ValueError, match="unsupported broker status"):
        store.record_broker_order("client-status-3", "broker-3", "")

    intent = store.get_unresolved("client-status-3")
    assert intent is not None
    assert intent.broker_order_id is None
    assert intent.broker_status is None
