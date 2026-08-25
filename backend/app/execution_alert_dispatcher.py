from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from typing import Callable

from app.execution_alert_events import ExecutionAlertEventStore, ExecutionAlertEvent


@dataclass(frozen=True)
class DispatchResult:
    event_id: int
    delivered: bool
    attempts: int


class ExecutionAlertDispatcher:
    """Retryable outbox dispatcher with durable delivery state."""

    def __init__(self, event_store: ExecutionAlertEventStore, path: str | None = None, publish: Callable[[ExecutionAlertEvent], None] | None = None, lease_seconds: float = 60.0) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.event_store = event_store
        self.path = path or event_store.path
        self.publish = publish or (lambda event: None)
        self.lease_seconds = lease_seconds
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alert_deliveries (event_id INTEGER PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, delivered_at TEXT, last_error TEXT, next_attempt_at TEXT, lease_token TEXT, lease_expires_at TEXT)")
            self._ensure_column(conn, "execution_alert_deliveries", "lease_token", "TEXT")
            self._ensure_column(conn, "execution_alert_deliveries", "lease_expires_at", "TEXT")
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def claim(self, event_id: int) -> str | None:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires = (now + timedelta(seconds=self.lease_seconds)).isoformat()
        token = secrets.token_urlsafe(24)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT delivered_at,lease_expires_at FROM execution_alert_deliveries WHERE event_id=?", (event_id,)).fetchone()
            if row and row[0]:
                return None
            conn.execute("INSERT OR IGNORE INTO execution_alert_deliveries(event_id,attempts) VALUES (?,0)", (event_id,))
            updated = conn.execute(
                "UPDATE execution_alert_deliveries SET lease_token=?,lease_expires_at=? WHERE event_id=? AND delivered_at IS NULL AND (lease_token IS NULL OR lease_expires_at IS NULL OR lease_expires_at <= ?)",
                (token, expires, event_id, now_iso),
            ).rowcount
            conn.commit()
        return token if updated == 1 else None

    def dispatch_once(self, event_id: int) -> DispatchResult:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT id,alert_id,event_type,created_at FROM execution_alert_events WHERE id=?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(f"execution alert event {event_id} not found")
        lease_token = self.claim(event_id)
        if lease_token is None:
            with sqlite3.connect(self.path) as conn:
                state = conn.execute("SELECT attempts,delivered_at FROM execution_alert_deliveries WHERE event_id=?", (event_id,)).fetchone()
            attempts = int(state[0]) if state else 0
            return DispatchResult(event_id, bool(state and state[1]), attempts)
        with sqlite3.connect(self.path) as conn:
            state = conn.execute("SELECT attempts FROM execution_alert_deliveries WHERE event_id=?", (event_id,)).fetchone()
            attempts = int(state[0]) if state else 0
        event = type("Event", (), {"event_id": int(row[0]), "alert_id": int(row[1]), "event_type": str(row[2]), "created_at": str(row[3])})()
        attempts += 1
        try:
            self.publish(event)
        except Exception as exc:
            next_attempt = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE execution_alert_deliveries SET attempts=?,last_error=?,next_attempt_at=?,lease_token=NULL,lease_expires_at=NULL WHERE event_id=? AND lease_token=? AND delivered_at IS NULL", (attempts, str(exc)[:500], next_attempt, event_id, lease_token))
                conn.commit()
            return DispatchResult(event_id, False, attempts)
        delivered_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute("UPDATE execution_alert_deliveries SET attempts=?,delivered_at=?,last_error=NULL,next_attempt_at=NULL,lease_token=NULL,lease_expires_at=NULL WHERE event_id=? AND lease_token=? AND delivered_at IS NULL", (attempts, delivered_at, event_id, lease_token)).rowcount
            conn.commit()
        return DispatchResult(event_id, updated == 1, attempts)
