from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.broker_oauth_state import BrokerOAuthState


def test_oauth_state_hash_is_not_raw_state() -> None:
    raw = "test-state-value"
    row = BrokerOAuthState(
        user_id=1,
        broker="upstox",
        account_label="primary",
        state_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    assert row.state_hash != raw
    assert len(row.state_hash) == 64


def test_oauth_state_requires_expiry() -> None:
    row = BrokerOAuthState(
        user_id=1,
        broker="upstox",
        account_label="primary",
        state_hash="b" * 64,
    )
    assert row.expires_at is None


def test_expired_state_is_distinguishable() -> None:
    row = BrokerOAuthState(
        user_id=1,
        broker="upstox",
        account_label="primary",
        state_hash="c" * 64,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert row.expires_at < datetime.now(timezone.utc)
