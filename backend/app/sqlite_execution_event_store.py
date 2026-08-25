from __future__ import annotations

import sqlite3
from threading import RLock

from app.execution_event_store import ExecutionEventStore


class SQLiteExecutionEventStore(ExecutionEventStore):
    """Durable local event-id store with a UNIQUE event_id constraint."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute("CREATE TABLE IF NOT EXISTS execution_events (event_id TEXT PRIMARY KEY)")
        self._connection.commit()

    def contains(self, event_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM execution_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return row is not None

    def record(self, event_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO execution_events(event_id) VALUES (?)", (event_id,)
            )
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()
