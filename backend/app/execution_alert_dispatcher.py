from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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

    def __init__(self, event_store: ExecutionAlertEventStore, path: str | None = None, publish: Callable[[ExecutionAlertEvent], None] | None = None) -> None:
        self.event_store = event_store
        self.path = path or event_store.path
        self.publish = publish or (lambda event: None)
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alert_deliveries (event_id INTEGER PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, delivered_at TEXT, last_error TEXT, next_attempt_at TEXT)")
            conn.commit()

    def dispatch_once(self, event_id: int) -> DispatchResult:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT id,alert_id,event_type,created_at FROM execution_alert_events WHERE id=?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(f"execution alert event {event_id} not found")
            state = conn.execute("SELECT attempts,delivered_at FROM execution_alert_deliveries WHERE event_id=?", (event_id,)).fetchone()
            attempts = int(state[0]) if state else 0
            if state and state[1]:
                return DispatchResult(event_id, True, attempts)
            conn.execute("INSERT OR IGNORE INTO execution_alert_deliveries(event_id,attempts) VALUES (?,0)", (event_id,))
            conn.commit()
        event = type("Event", (), {"event_id": int(row[0]), "alert_id": int(row[1]), "event_type": str(row[2]), "created_at": str(row[3])})()
        attempts += 1
        try:
            self.publish(event)
        except Exception as exc:
            next_attempt = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE execution_alert_deliveries SET attempts=?,last_error=?,next_attempt_at=? WHERE event_id=?", (attempts, str(exc)[:500], next_attempt, event_id))
                conn.commit()
            return DispatchResult(event_id, False, attempts)
        delivered_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE execution_alert_deliveries SET attempts=?,delivered_at=?,last_error=NULL,next_attempt_at=NULL WHERE event_id=?", (attempts, delivered_at, event_id))
            conn.commit()
        return DispatchResult(event_id, True, attempts)
