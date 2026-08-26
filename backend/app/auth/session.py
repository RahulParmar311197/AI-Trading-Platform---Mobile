from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class UserSession:
    user_id: str
    role: str
    expires_at: int


class SessionAuthenticator:
    """Small stateless session verifier; tokens are signed, never stored in the mobile client as secrets."""

    def __init__(self, secret: str | None = None) -> None:
        self.secret = secret or os.getenv("APP_SESSION_SECRET", "")
        if not self.secret:
            raise RuntimeError("APP_SESSION_SECRET is required")

    def verify(self, token: str | None) -> UserSession:
        if not token:
            raise ValueError("authentication required")
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(self.secret.encode(), encoded.encode(), hashlib.sha256).digest()
            supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            if not hmac.compare_digest(expected, supplied):
                raise ValueError("invalid session")
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if int(payload["exp"]) <= int(time.time()):
                raise ValueError("session expired")
            return UserSession(str(payload["sub"]), str(payload.get("role", "user")), int(payload["exp"]))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid session") from exc
