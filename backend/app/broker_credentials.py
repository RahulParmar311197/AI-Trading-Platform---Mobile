from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class BrokerCredentialVault:
    """Encrypt/decrypt broker credentials using the configured application key.

    The vault deliberately has no logging and accepts only JSON-serializable
    mappings. A missing key is a hard configuration error rather than a reason
    to persist plaintext credentials.
    """

    def __init__(self, key: str | None = None) -> None:
        configured = key if key is not None else get_settings().broker_credentials_key
        if not configured:
            raise RuntimeError("BROKER_CREDENTIALS_KEY is required")
        try:
            raw = base64.urlsafe_b64decode(configured.encode("ascii"))
            if len(raw) != 32:
                raise ValueError
            self._fernet = Fernet(configured.encode("ascii"))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RuntimeError("BROKER_CREDENTIALS_KEY must be a valid Fernet key") from exc

    @staticmethod
    def _canonical(credentials: dict[str, Any]) -> bytes:
        if not isinstance(credentials, dict) or not credentials:
            raise ValueError("credentials must be a non-empty mapping")
        return json.dumps(
            credentials, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def encrypt(self, credentials: dict[str, Any]) -> str:
        return self._fernet.encrypt(self._canonical(credentials)).decode("ascii")

    def decrypt(self, token: str) -> dict[str, Any]:
        if not token:
            raise ValueError("encrypted credentials are required")
        try:
            plaintext = self._fernet.decrypt(token.encode("ascii"))
            value = json.loads(plaintext.decode("utf-8"))
        except (InvalidToken, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid encrypted broker credentials") from exc
        if not isinstance(value, dict) or not value:
            raise ValueError("decrypted broker credentials are invalid")
        return value

    def fingerprint(self, credentials: dict[str, Any]) -> str:
        """Return a non-secret deterministic fingerprint for diagnostics/deduping."""
        return hmac.new(
            self._fernet._signing_key,
            self._canonical(credentials),
            hashlib.sha256,
        ).hexdigest()
