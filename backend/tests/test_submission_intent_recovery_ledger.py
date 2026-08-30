from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.submission_intent import SubmissionIntentRecord
from app.submission_intent_store import SubmissionIntentStore


def _store(tmp_path: Path) -> SubmissionIntentStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine, tables=[SubmissionIntentRecord.__table__])
    return SubmissionIntentStore(session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False))


def test_broker_binding_is_durable_before_resolution(tmp_path: Path):
    store = _store(tmp_path)
    store.create(client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY", side="BUY", quantity=10, request_fingerprint="fp-1")
    store.record_broker_order("cli-1", "broker-99", "FILLED")
    restarted = _store(tmp_path)
    intent = restarted.unresolved()[0]
    assert intent.broker_order_id == "broker-99"
    assert intent.broker_status == "FILLED"
    assert intent.recovered_at is not None
    restarted.resolve("cli-1")
    assert restarted.unresolved_count() == 0


def test_conflicting_broker_order_binding_fails_closed(tmp_path: Path):
    store = _store(tmp_path)
    store.create(client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY", side="BUY", quantity=10, request_fingerprint="fp-1")
    store.record_broker_order("cli-1", "broker-99", "NEW")
    with pytest.raises(RuntimeError, match="different broker order"):
        store.record_broker_order("cli-1", "broker-100", "FILLED")
    intent = store.unresolved()[0]
    assert intent.broker_order_id == "broker-99"
    assert intent.broker_status == "NEW"


def test_resolution_without_broker_binding_is_rejected(tmp_path: Path):
    store = _store(tmp_path)
    store.create(client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY", side="BUY", quantity=10, request_fingerprint="fp-1")
    with pytest.raises(RuntimeError, match="before broker order is durably bound"):
        store.resolve("cli-1")
    assert store.unresolved_count() == 1
