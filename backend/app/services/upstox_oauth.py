from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.broker_oauth_state import BrokerOAuthState


class UpstoxOAuthService:
    """Creates authenticated Upstox OAuth authorization requests."""

    provider = "upstox"
    authorization_endpoint = "https://api.upstox.com/v2/login/authorization/dialog"

    def __init__(self, db: Session, *, state_ttl_seconds: int = 600) -> None:
        if state_ttl_seconds <= 0:
            raise ValueError("state_ttl_seconds must be positive")
        self.db = db
        self.state_ttl = timedelta(seconds=state_ttl_seconds)
        self.settings = get_settings()

    @staticmethod
    def _hash_state(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def create_authorization_url(self, *, user_id: int, account_label: str) -> str:
        label = account_label.strip()
        if not label or len(label) > 80:
            raise ValueError("account_label is required and must be at most 80 characters")
        if not self.settings.upstox_client_id or not self.settings.upstox_redirect_uri:
            raise RuntimeError("Upstox OAuth configuration is incomplete")

        state = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        self.db.add(
            BrokerOAuthState(
                user_id=user_id,
                broker=self.provider,
                account_label=label,
                state_hash=self._hash_state(state),
                expires_at=now + self.state_ttl,
                used=False,
            )
        )
        self.db.commit()

        params = {
            "client_id": self.settings.upstox_client_id,
            "redirect_uri": self.settings.upstox_redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return self.authorization_endpoint + "?" + urlencode(params)
