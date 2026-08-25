from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Callable

from app.execution_alert_store import ExecutionAlertRecord


@dataclass(frozen=True)
class ExecutionAlertEvent:
    event_id: int
    alert_id: int
    event_type: str
    created_at: str


class ExecutionAlertEventStore:
    """Durable outbox for exactly-once event creation per alert lifecycle transition."""

    def __init__(self, path: str = "execution_alert_events.db") -> None:
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alert_events (id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL, event_type TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(alert_id, event_type))")
            conn.commit()

    def emit_once(self, alert: ExecutionAlertRecord, event_type: str) -> ExecutionAlertEvent | None:
        if event_type not in {"CREATED", "ACKNOWLEDGED", "RESOLVED"}:
            raise ValueError("invalid execution alert event type")
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute("INSERT OR IGNORE INTO execution_alert_events(alert_id,event_type,created_at) VALUES (?,?,?)", (alert.alert_id, event_type, created_at))
            conn.commit()
            if cursor.rowcount != 1:
                return None
            return ExecutionAlertEvent(int(cursor.lastrowid), alert.alert_id, event_type, created_at)


class ExecutionAlertEventPublisher:
    """Best-effort publisher; durable event creation is never allowed to block execution."""

    def __init__(self, store: ExecutionAlertEventStore, publish: Callable[[ExecutionAlertEvent], None] | None = None) -> None:
        self.store = store
        self.publish = publish or (lambda event: None)

    def publish_once(self, alert: ExecutionAlertRecord, event_type: str) -> ExecutionAlertEvent | None:
        try:
            event = self.store.emit_once(alert, event_type)
            if event is not None:
                self.publish(event)
            return event
        except Exception:
            return None
