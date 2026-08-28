from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.oauth_state import OAuthState


class OAuthStateStore:
    """Transactional, one-time OAuth state storage.

    Raw state values are returned only to the caller that creates them; only a
    SHA-256 digest is persisted. Consumption is conditional on provider, user,
    expiry, and an unconsumed row so replay attempts cannot succeed.
    """

    def __init__(self, session_factory, *, ttl_seconds: int = 600):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._session_factory = session_factory
        self._ttl = timedelta(seconds=ttl_seconds)

    @staticmethod
    def _hash(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def create(self, *, user_id: int, provider: str) -> str:
        raw_state = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:  # type: Session
            session.add(
                OAuthState(
                    state_hash=self._hash(raw_state),
                    user_id=user_id,
                    provider=provider,
                    created_at=now,
                    expires_at=now + self._ttl,
                )
            )
            session.commit()
        return raw_state

    def consume(self, *, state: str, user_id: int, provider: str) -> bool:
        now = datetime.now(timezone.utc)
        digest = self._hash(state)
        with self._session_factory() as session:  # type: Session
            result = session.execute(
                update(OAuthState)
                .where(
                    OAuthState.state_hash == digest,
                    OAuthState.user_id == user_id,
                    OAuthState.provider == provider,
                    OAuthState.consumed_at.is_(None),
                    OAuthState.expires_at > now,
                )
                .values(consumed_at=now)
            )
            session.commit()
            return result.rowcount == 1

    def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:  # type: Session
            rows = session.scalars(
                select(OAuthState).where(OAuthState.expires_at <= now)
            ).all()
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)
