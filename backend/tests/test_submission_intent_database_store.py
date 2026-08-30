from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.submission_intent_store import SubmissionIntentStore


def _factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'submission-intents.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["submission_intents"]])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _create(store: SubmissionIntentStore):
    try:
        store.create(
            client_order_id="cli-db-1",
            route="upstox",
            account_id="001",
            symbol="NIFTY",
            side="BUY",
            quantity=1,
            request_fingerprint="fp-1",
        )
    except Exception as exc:
        return type(exc).__name__
    return "created"


def test_database_store_survives_new_store_instance(tmp_path):
    session_factory = _factory(tmp_path)
    first = SubmissionIntentStore(session_factory=session_factory)
    first.create(
        client_order_id="cli-db-1",
        route="upstox",
        account_id="001",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-1",
    )

    second = SubmissionIntentStore(session_factory=session_factory)
    assert second.unresolved_count() == 1
    assert second.unresolved()[0].account_id == "001"


def test_database_store_unique_client_order_id_wins_concurrent_race(tmp_path):
    session_factory = _factory(tmp_path)
    stores = [SubmissionIntentStore(session_factory=session_factory) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(_create, stores))

    assert outcomes == ["RuntimeError", "created"]
    assert stores[0].unresolved_count() == 1


def test_database_store_resolved_intent_can_be_reused_without_leaving_duplicate_unresolved_rows(tmp_path):
    session_factory = _factory(tmp_path)
    store = SubmissionIntentStore(session_factory=session_factory)
    store.create(
        client_order_id="cli-db-1",
        route="upstox",
        account_id="001",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-1",
    )
    store.resolve("cli-db-1")
    store.create(
        client_order_id="cli-db-1",
        route="upstox",
        account_id="001",
        symbol="NIFTY",
        side="SELL",
        quantity=1,
        request_fingerprint="fp-2",
    )

    unresolved = store.unresolved()
    assert len(unresolved) == 1
    assert unresolved[0].side == "SELL"
    assert unresolved[0].request_fingerprint == "fp-2"
