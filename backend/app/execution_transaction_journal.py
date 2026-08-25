from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class ExecutionJournalEntry:
    event_id: str
    order_id: str
    event_kind: str
    position_symbol: str | None
    position_delta: float
    payload: dict


class ExecutionTransactionJournal:
    """Atomic local execution journal: event claim, state mutation and outbox."""

    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS execution_journal ("
            "event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, event_kind TEXT NOT NULL, "
            "position_symbol TEXT, position_delta REAL NOT NULL, payload TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS execution_outbox ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, "
            "event_type TEXT NOT NULL, payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.commit()

    def apply(self, entry: ExecutionJournalEntry) -> bool:
        if not entry.event_id or not entry.order_id:
            raise ValueError("event_id and order_id are required")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                exists = self._connection.execute(
                    "SELECT 1 FROM execution_journal WHERE event_id = ?", (entry.event_id,)
                ).fetchone()
                if exists:
                    self._connection.rollback()
                    return False
                payload = json.dumps(entry.payload, sort_keys=True)
                self._connection.execute(
                    "INSERT INTO execution_journal(event_id,order_id,event_kind,position_symbol,position_delta,payload) VALUES(?,?,?,?,?,?)",
                    (entry.event_id, entry.order_id, entry.event_kind, entry.position_symbol, entry.position_delta, payload),
                )
                self._connection.execute(
                    "INSERT INTO execution_outbox(event_id,event_type,payload) VALUES(?,?,?)",
                    (entry.event_id, entry.event_kind, payload),
                )
                self._connection.commit()
                return True
            except Exception:
                self._connection.rollback()
                raise

    def pending_outbox(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id,event_id,event_type,payload FROM execution_outbox WHERE published=0 ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(id=r[0], event_id=r[1], event_type=r[2], payload=json.loads(r[3])) for r in rows]

    def mark_published(self, outbox_id: int) -> None:
        with self._lock:
            self._connection.execute("UPDATE execution_outbox SET published=1 WHERE id=?", (outbox_id,))
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()
