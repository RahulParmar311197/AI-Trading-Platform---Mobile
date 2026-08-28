from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.broker_oauth_state import BrokerOAuthState


class OAuthStateStore:
    """Transactional, one-time broker OAuth state storage.

    Raw state values are returned only to the caller that creates them; only a
    SHA-256 digest is persisted. Consumption is conditional on broker, user,
    expiry, and an unused row so replay attempts cannot succeed.
    """

    def __init__(self, session_factory, *, ttl_seconds: int = 600):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._session_factory = session_factory
        self._ttl = timedelta(seconds=ttl_seconds)

    @staticmethod
    def _hash(state: str) -> str:
        if not isinstance(state, str) or not state:
            raise ValueError("state must be a non-empty string")
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def create(self, *, user_id: int, broker: str, account_label: str) -> str:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        if not isinstance(broker, str) or not broker.strip():
            raise ValueError("broker must be non-empty")
        if not isinstance(account_label, str) or not account_label.strip():
            raise ValueError("account_label must be non-empty")

        raw_state = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:  # type: Session
            session.add(
                BrokerOAuthState(
                    state_hash=self._hash(raw_state),
                    user_id=user_id,
                    broker=broker.strip(),
                    account_label=account_label.strip(),
                    expires_at=now + self._ttl,
                    used=False,
                    created_at=now,
                )
            )
            session.commit()
        return raw_state

    def consume(self, *, state: str, user_id: int, broker: str) -> bool:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        if not isinstance(broker, str) or not broker.strip():
            raise ValueError("broker must be non-empty")

        now = datetime.now(timezone.utc)
        digest = self._hash(state)
        with self._session_factory() as session:  # type: Session
            result = session.execute(
                update(BrokerOAuthState)
                .where(
                    BrokerOAuthState.state_hash == digest,
                    BrokerOAuthState.user_id == user_id,
                    BrokerOAuthState.broker == broker.strip(),
                    BrokerOAuthState.used.is_(False),
                    BrokerOAuthState.expires_at > now,
                )
                .values(used=True)
            )
            session.commit()
            return result.rowcount == 1

    def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:  # type: Session
            result = session.execute(
                select(BrokerOAuthState.id).where(BrokerOAuthState.expires_at <= now)
            )
            ids = [row[0] for row in result]
            if ids:
                session.execute(
                    BrokerOAuthState.__table__.delete().where(BrokerOAuthState.id.in_(ids))
                )
            session.commit()
            return len(ids)
