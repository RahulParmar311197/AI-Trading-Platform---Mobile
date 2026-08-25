from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from threading import RLock


class DurableExecutionConsumer:
    """Durably deduplicate outbox deliveries before invoking downstream effects."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS consumed_execution_events(event_id TEXT PRIMARY KEY, consumed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        self._db.commit()

    def consume(self, message: dict, handler: Callable[[dict], None]) -> bool:
        event_id = message.get("event_id")
        if not event_id:
            raise ValueError("event_id is required")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT 1 FROM consumed_execution_events WHERE event_id=?", (event_id,)).fetchone()
                if row:
                    self._db.commit()
                    return False
                handler(message)
                self._db.execute("INSERT INTO consumed_execution_events(event_id) VALUES(?)", (event_id,))
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._db.close()
