from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import sqlite3
from threading import RLock
from typing import Callable, Protocol


class AuthorizationRecord(Protocol):
    _nonce: str
    _order_fingerprint: str
    _context_key: str
    _expires_at: datetime


class ExecutionAuthorizationStore:
    """Durable, atomic store for single-use execution authorizations."""

    def __init__(self, path: str = "data/execution_authorizations.sqlite3") -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_authorizations (
                nonce_hash TEXT PRIMARY KEY,
                order_fingerprint TEXT NOT NULL,
                context_key TEXT NOT NULL DEFAULT '',
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            )
            """
        )
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(execution_authorizations)")}
        if "context_key" not in columns:
            self._connection.execute("ALTER TABLE execution_authorizations ADD COLUMN context_key TEXT NOT NULL DEFAULT ''")

    def issue(self, authorization: AuthorizationRecord) -> None:
        if not authorization._context_key.strip():
            raise ValueError("authorization context key is required")
        with self._lock:
            self._connection.execute(
                "INSERT INTO execution_authorizations (nonce_hash, order_fingerprint, context_key, expires_at, consumed_at) VALUES (?, ?, ?, ?, NULL)",
                (_hash_nonce(authorization._nonce), authorization._order_fingerprint, authorization._context_key, authorization._expires_at.isoformat()),
            )

    def consume(self, authorization: AuthorizationRecord, order_fingerprint: str, context_key: str, now: Callable[[], datetime]) -> str:
        current = now()
        if current.tzinfo is None:
            raise ValueError("authorization clock must be timezone-aware")
        if not context_key.strip():
            raise ValueError("execution context key is required")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute("SELECT order_fingerprint, context_key, expires_at, consumed_at FROM execution_authorizations WHERE nonce_hash = ?", (_hash_nonce(authorization._nonce),)).fetchone()
                if row is None:
                    self._connection.execute("ROLLBACK")
                    return "missing"
                stored_fingerprint, stored_context_key, expires_at, consumed_at = row
                if consumed_at is not None:
                    self._connection.execute("ROLLBACK")
                    return "consumed"
                if stored_fingerprint != order_fingerprint:
                    self._connection.execute("ROLLBACK")
                    return "order_mismatch"
                if stored_context_key != context_key:
                    self._connection.execute("ROLLBACK")
                    return "context_mismatch"
                expiry = datetime.fromisoformat(expires_at)
                if expiry.tzinfo is None:
                    self._connection.execute("ROLLBACK")
                    return "invalid_expiry"
                if expiry < current:
                    self._connection.execute("ROLLBACK")
                    return "expired"
                consumed_at = current.astimezone(timezone.utc).isoformat()
                updated = self._connection.execute("UPDATE execution_authorizations SET consumed_at = ? WHERE nonce_hash = ? AND consumed_at IS NULL", (consumed_at, _hash_nonce(authorization._nonce))).rowcount
                if updated != 1:
                    self._connection.execute("ROLLBACK")
                    return "consumed"
                self._connection.execute("COMMIT")
                return "consumed_now"
            except Exception:
                self._connection.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def _hash_nonce(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()
