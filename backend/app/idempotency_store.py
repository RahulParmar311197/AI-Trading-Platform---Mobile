from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


class IdempotencyStore:
    """SQLite-backed claim store shared by application workers on the same host."""

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
