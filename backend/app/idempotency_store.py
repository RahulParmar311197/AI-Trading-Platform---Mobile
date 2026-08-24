from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from contextlib import contextmanager


class IdempotencyStore:
    """SQLite-backed execution claim store shared by application workers/processes."""

    def __init__(self, path: str = "data/idempotency.sqlite3"):
        self.path = Path(path)
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("CREATE TABLE IF NOT EXISTS execution_claims (client_order_id TEXT PRIMARY KEY, state TEXT NOT NULL, execution_id TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(execution_claims)")}
            if "execution_id" not in columns: db.execute("ALTER TABLE execution_claims ADD COLUMN execution_id TEXT")
            if "updated_at" not in columns: db.execute("ALTER TABLE execution_claims ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
            db.commit()

    @contextmanager
    def _connect(self):
        with sqlite3.connect(self.path, timeout=5, isolation_level="IMMEDIATE") as db:
            db.execute("PRAGMA busy_timeout=5000")
            yield db

    def claim(self, client_order_id: str, execution_id: str | None = None) -> bool:
        key = str(client_order_id).strip()
        if not key: raise ValueError("client_order_id is required")
        with self._lock, self._connect() as db:
            cursor = db.execute("INSERT OR IGNORE INTO execution_claims(client_order_id, state, execution_id) VALUES (?, 'CLAIMED', ?)", (key, execution_id))
            db.commit()
            return cursor.rowcount == 1

    def get_state(self, client_order_id: str) -> str | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT state FROM execution_claims WHERE client_order_id = ?", (str(client_order_id).strip(),)).fetchone()
            return str(row[0]) if row else None

    def get_claim(self, client_order_id: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT client_order_id, state, execution_id, updated_at FROM execution_claims WHERE client_order_id = ?", (str(client_order_id).strip(),)).fetchone()
            return {"client_order_id": row[0], "state": row[1], "execution_id": row[2], "updated_at": row[3]} if row else None

    def mark_completed(self, client_order_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("UPDATE execution_claims SET state = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE client_order_id = ?", (str(client_order_id).strip(),))
            db.commit()

    def release(self, client_order_id: str) -> None:
        """Explicitly release only a claim that never reached broker submission."""
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM execution_claims WHERE client_order_id = ? AND state = 'CLAIMED'", (str(client_order_id).strip(),))
            db.commit()
