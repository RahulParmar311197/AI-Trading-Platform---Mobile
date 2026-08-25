from __future__ import annotations

import json
import sqlite3
from threading import RLock


class ExecutionEventQuarantine:
    """Durable fail-closed quarantine for broker events that cannot be safely resolved."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._database_path = database_path
        self._db = sqlite3.connect(database_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS execution_event_quarantine(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,broker TEXT NOT NULL,broker_order_id TEXT,payload TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'OPEN',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        self._db.commit()

    @property
    def database_path(self) -> str:
        return self._database_path

    def quarantine(self, *, event_id: str, broker: str, broker_order_id: str, payload: dict, reason: str) -> bool:
        if not event_id or not broker or not reason:
            raise ValueError("event_id, broker and reason are required")
        with self._lock:
            cursor = self._db.execute("INSERT OR IGNORE INTO execution_event_quarantine(event_id,broker,broker_order_id,payload,reason) VALUES(?,?,?,?,?)", (event_id, broker, broker_order_id, json.dumps(payload, sort_keys=True), reason))
            self._db.commit()
            return cursor.rowcount == 1

    def pending(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id,event_id,broker,broker_order_id,payload,reason,status,created_at FROM execution_event_quarantine WHERE status='OPEN' ORDER BY id LIMIT ?", (limit,)).fetchall()
        return [dict(id=r[0], event_id=r[1], broker=r[2], broker_order_id=r[3], payload=json.loads(r[4]), reason=r[5], status=r[6], created_at=r[7]) for r in rows]

    def list_recovery_cases(self, limit: int = 100) -> list[dict]:
        """Return open cases for review; this method never binds or executes them."""
        return self.pending(limit)

    def resolve(self, quarantine_id: int) -> None:
        """Direct resolution is forbidden; execution and quarantine must resolve atomically."""
        raise RuntimeError("direct quarantine resolution is disabled; use TransactionalRecoveryService.approve_and_apply")

    def close(self) -> None:
        with self._lock:
            self._db.close()
