from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.execution_alert_events import ExecutionAlertEventPublisher


@dataclass(frozen=True)
class ExecutionAlertRecord:
    alert_id: int
    created_at: str
    severity: str
    reason_codes: tuple[str, ...]
    fingerprint: str
    status: str = "OPEN"
    acknowledged_at: str | None = None
    resolved_at: str | None = None


@dataclass(frozen=True)
class ExecutionAlertPage:
    records: list[ExecutionAlertRecord]
    total: int
    limit: int
    offset: int


class ExecutionAlertStore:
    """Durable SQLite-backed execution alert history and lifecycle."""

    def __init__(self, path: str = "execution_alerts.db", event_publisher: ExecutionAlertEventPublisher | None = None) -> None:
        self.path = path
        self.event_publisher = event_publisher
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, severity TEXT NOT NULL, reason_codes TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', acknowledged_at TEXT, resolved_at TEXT)")
            for column, definition in (("status", "TEXT NOT NULL DEFAULT 'OPEN'"), ("acknowledged_at", "TEXT"), ("resolved_at", "TEXT")):
                try: conn.execute(f"ALTER TABLE execution_alerts ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError: pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_fingerprint_created ON execution_alerts(fingerprint, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_status ON execution_alerts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_severity_created ON execution_alerts(severity, created_at DESC)")
