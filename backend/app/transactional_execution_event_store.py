from __future__ import annotations

import sqlite3
from threading import RLock


class TransactionalExecutionEventStore:
    """SQLite-backed atomic event claim boundary.

    claim() returns True only for the first successful claim of an event_id.
    The unique primary key makes duplicate delivery safe across restarts/processes
    sharing the same database.
    """

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS execution_event_claims ("
            "event_id TEXT PRIMARY KEY, claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.commit()

    def claim(self, event_id: str) -> bool:
        if not event_id:
            raise ValueError("event_id is required")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._connection.execute(
                    "INSERT OR IGNORE INTO execution_event_claims(event_id) VALUES (?)",
                    (event_id,),
                )
                self._connection.commit()
                return cursor.rowcount == 1
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()
