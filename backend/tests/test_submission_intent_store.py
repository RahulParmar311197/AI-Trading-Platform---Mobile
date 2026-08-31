from multiprocessing import Barrier, Process, Queue
from pathlib import Path

import pytest

from app.submission_intent_store import SubmissionIntentStore


def _create(store: SubmissionIntentStore, client_id: str = "cli-1", fingerprint: str = "fp-123"):
    return store.create(
        client_order_id=client_id,
        route="live",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        request_fingerprint=fingerprint,
    )


def test_submission_intent_survives_new_store_instance(tmp_path: Path):
    path = tmp_path / "intents.json"
    first = SubmissionIntentStore(str(path))
    intent = _create(first)

    second = SubmissionIntentStore(str(path))
    unresolved = second.unresolved()
    assert len(unresolved) == 1
    assert unresolved[0].client_order_id == intent.client_order_id
    assert second.unresolved_count() == 1


def test_resolved_intent_is_not_unresolved_after_restart(tmp_path: Path):
    path = tmp_path / "intents.json"
    first = SubmissionIntentStore(str(path))
    _create(first)
    first.record_broker_order("cli-1", "broker-1", "FILLED")
    first.resolve("cli-1")

    second = SubmissionIntentStore(str(path))
    assert second.unresolved() == []
    assert second.unresolved_count() == 0


def test_resolved_client_order_id_reopens_clean_lifecycle(tmp_path: Path):
    path = tmp_path / "intents.json"
    store = SubmissionIntentStore(str(path))
    _create(store)
    store.record_broker_order("cli-1", "broker-old", "FILLED")
    store.resolve("cli-1")

    reopened = store.create(
        client_order_id="cli-1",
        route="upstox",
        account_id="acct-2",
        symbol="BANKNIFTY",
        side="SELL",
        quantity=5,
        request_fingerprint="fp-new",
    )

    assert reopened.client_order_id == "cli-1"
    assert reopened.route == "upstox"
    assert reopened.account_id == "acct-2"
    assert reopened.symbol == "BANKNIFTY"
    assert reopened.side == "SELL"
    assert reopened.quantity == 5
    assert reopened.request_fingerprint == "fp-new"
    assert reopened.resolved_at is None
    assert reopened.broker_order_id is None
    assert reopened.broker_status is None
    assert reopened.recovered_at is None
    assert store.get_unresolved("cli-1") == reopened


def test_same_unresolved_intent_is_idempotent_for_same_fingerprint(tmp_path: Path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    first = _create(store)
    replay = _create(store)
    assert replay == first
    assert store.unresolved_count() == 1


def test_unresolved_intent_fingerprint_mismatch_is_rejected(tmp_path: Path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    _create(store)
    with pytest.raises(RuntimeError, match="fingerprint mismatch"):
        _create(store, fingerprint="different-request")


def test_corrupt_primary_recovers_last_durable_snapshot(tmp_path: Path):
    path = tmp_path / "intents.json"
    store = SubmissionIntentStore(str(path))
    _create(store, "cli-1")
    store.record_broker_order("cli-1", "broker-1", "FILLED")
    store.resolve("cli-1")
    _create(store, "cli-2")
    path.write_text("{corrupt", encoding="utf-8")

    restored = SubmissionIntentStore(str(path))
    assert restored.unresolved() == []


def _concurrent_create(path: str, barrier: Barrier, results: Queue) -> None:
    store = SubmissionIntentStore(path)
    barrier.wait()
    try:
        _create(store)
    except Exception as exc:
        results.put(type(exc).__name__)
    else:
        results.put("created")


def test_same_unresolved_intent_is_idempotent_across_processes(tmp_path: Path):
    path = tmp_path / "intents.json"
    barrier = Barrier(2)
    results = Queue()
    workers = [
        Process(target=_concurrent_create, args=(str(path), barrier, results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0

    outcomes = sorted(results.get(timeout=2) for _ in workers)
    assert outcomes == ["created", "created"]
    assert SubmissionIntentStore(str(path)).unresolved_count() == 1
