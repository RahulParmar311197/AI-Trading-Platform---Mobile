from pathlib import Path

import pytest

from app.submission_intent_store import SubmissionIntentStore


def _create(store: SubmissionIntentStore, client_id: str = "cli-1"):
    return store.create(
        client_order_id=client_id,
        route="live",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        request_fingerprint="fp-123",
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
    first.resolve("cli-1")

    second = SubmissionIntentStore(str(path))
    assert second.unresolved() == []
    assert second.unresolved_count() == 0


def test_duplicate_unresolved_intent_is_rejected(tmp_path: Path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    _create(store)
    with pytest.raises(RuntimeError, match="unresolved submission intent"):
        _create(store)


def test_corrupt_primary_recovers_from_backup(tmp_path: Path):
    path = tmp_path / "intents.json"
    store = SubmissionIntentStore(str(path))
    _create(store, "cli-1")
    store.resolve("cli-1")
    _create(store, "cli-2")
    path.write_text("{corrupt", encoding="utf-8")

    restored = SubmissionIntentStore(str(path))
    unresolved = restored.unresolved()
    assert [item.client_order_id for item in unresolved] == ["cli-1"]
