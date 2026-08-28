from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.broker_oauth_state import BrokerOAuthState
from app.oauth_state_store import OAuthStateStore


def _store():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[BrokerOAuthState.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, OAuthStateStore(Session, ttl_seconds=60), Session


def test_create_persists_hash_only_and_consumes_once():
    engine, store, Session = _store()
    try:
        raw = store.create(user_id=7, broker="upstox", account_label="primary")
        with Session() as session:
            row = session.scalar(select(BrokerOAuthState))
            assert row is not None
            assert row.state_hash != raw
            assert len(row.state_hash) == 64
            assert row.account_label == "primary"
            assert row.used is False

        assert store.consume(state=raw, user_id=7, broker="upstox") is True
        assert store.consume(state=raw, user_id=7, broker="upstox") is False
    finally:
        engine.dispose()


def test_consume_rejects_wrong_user_or_broker_without_consuming():
    engine, store, Session = _store()
    try:
        raw = store.create(user_id=7, broker="upstox", account_label="primary")
        assert store.consume(state=raw, user_id=8, broker="upstox") is False
        assert store.consume(state=raw, user_id=7, broker="other") is False
        assert store.consume(state=raw, user_id=7, broker="upstox") is True
    finally:
        engine.dispose()


def test_expired_state_cannot_be_consumed_and_can_be_purged():
    engine, store, Session = _store()
    try:
        raw = store.create(user_id=7, broker="upstox", account_label="primary")
        with Session() as session:
            row = session.scalar(select(BrokerOAuthState))
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.commit()

        assert store.consume(state=raw, user_id=7, broker="upstox") is False
        assert store.purge_expired() == 1
        with Session() as session:
            assert session.scalar(select(BrokerOAuthState)) is None
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"user_id": 0, "broker": "upstox", "account_label": "primary"},
        {"user_id": 7, "broker": "", "account_label": "primary"},
        {"user_id": 7, "broker": "upstox", "account_label": ""},
    ],
)
def test_create_rejects_invalid_identity(kwargs):
    _, store, _ = _store()
    with pytest.raises(ValueError):
        store.create(**kwargs)
