from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


class IdempotencyStore:
    """SQLite-backed execution claim store shared by application workers."""

    def __init__(self, path: str = "data/idempotency.sqlite3"):
        self.path = Path(path)
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS execution_claims (client_order_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.commit()

    def claim(self, client_order_id: str) -> bool:
        with self._lock, sqlite3.connect(self.path) as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO execution_claims(client_order_id, state) VALUES (?, 'CLAIMED')",
                (client_order_id,),
            )
            db.commit()
            return cursor.rowcount == 1

    def get_state(self, client_order_id: str) -> str | None:
        with self._lock, sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT state FROM execution_claims WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
            return str(row[0]) if row else None

    def mark_completed(self, client_order_id: str) -> None:
        with self._lock, sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE execution_claims SET state = 'COMPLETED' WHERE client_order_id = ?",
                (client_order_id,),
            )
            db.commit()
