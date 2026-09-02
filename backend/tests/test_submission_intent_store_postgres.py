import pytest

from app.db import SessionLocal
from app.models.submission_intent import SubmissionIntentRecord
from app.submission_intent_store import SubmissionIntentStore


def _create(store: SubmissionIntentStore, client_id: str = "pg-cli-1", fingerprint: str = "pg-fp-1"):
    return store.create(
        client_order_id=client_id,
        route="live",
        account_id="acct-pg-1",
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        request_fingerprint=fingerprint,
    )


def _delete(client_id: str) -> None:
    session = SessionLocal()
    try:
        with session.begin():
            record = session.get(SubmissionIntentRecord, client_id)
            if record is not None:
                session.delete(record)
    finally:
        session.close()


def test_postgres_resolved_client_order_id_is_immutable():
    client_id = "pg-cli-immutable-1"
    store = SubmissionIntentStore(session_factory=SessionLocal)
    _delete(client_id)
    try:
        _create(store, client_id)
        store.record_broker_order(client_id, "broker-pg-1", "FILLED")
        store.resolve(client_id)

        with pytest.raises(RuntimeError, match="already been resolved"):
            _create(store, client_id, fingerprint="new-pg-request")

        session = SessionLocal()
        try:
            record = session.get(SubmissionIntentRecord, client_id)
            assert record is not None
            assert record.resolved_at is not None
            assert record.broker_order_id == "broker-pg-1"
            assert record.request_fingerprint == "pg-fp-1"
        finally:
            session.close()
    finally:
        _delete(client_id)


def test_postgres_unresolved_replay_remains_idempotent():
    client_id = "pg-cli-replay-1"
    store = SubmissionIntentStore(session_factory=SessionLocal)
    _delete(client_id)
    try:
        first = _create(store, client_id)
        replay = _create(store, client_id)
        assert replay == first
        assert store.unresolved_count() == 1
    finally:
        _delete(client_id)
