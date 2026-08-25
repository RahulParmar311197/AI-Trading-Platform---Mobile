from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3


@dataclass(frozen=True)
class WorkerHealth:
    status: str
    last_started_at: str | None
    last_tick_at: str | None
    last_success_at: str | None
    processed_total: int
    delivered_total: int
    failed_total: int
    pending: int
    dead_lettered: int


class ExecutionAlertWorkerHealth:
    def __init__(self, path: str) -> None:
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alert_worker_health (id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL, last_started_at TEXT, last_tick_at TEXT, last_success_at TEXT, processed_total INTEGER NOT NULL DEFAULT 0, delivered_total INTEGER NOT NULL DEFAULT 0, failed_total INTEGER NOT NULL DEFAULT 0)")
            conn.execute("INSERT OR IGNORE INTO execution_alert_worker_health(id,status) VALUES (1,'STARTING')")
            conn.commit()

    def started(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE execution_alert_worker_health SET status='RUNNING',last_started_at=?,last_tick_at=? WHERE id=1", (now, now))
            conn.commit()

    def tick(self, processed: int, delivered: int, failed: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE execution_alert_worker_health SET status='RUNNING',last_tick_at=?,last_success_at=?,processed_total=processed_total+?,delivered_total=delivered_total+?,failed_total=failed_total+? WHERE id=1", (now, now, processed, delivered, failed))
            conn.commit()

    def stopped(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE execution_alert_worker_health SET status='STOPPED' WHERE id=1")
            conn.commit()

    def snapshot(self) -> WorkerHealth:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT status,last_started_at,last_tick_at,last_success_at,processed_total,delivered_total,failed_total FROM execution_alert_worker_health WHERE id=1").fetchone()
            pending = int(conn.execute("SELECT COUNT(*) FROM execution_alert_deliveries WHERE delivered_at IS NULL AND event_id NOT IN (SELECT event_id FROM execution_alert_dead_letters)").fetchone()[0]) if self._table_exists(conn, 'execution_alert_deliveries') else 0
            dead = int(conn.execute("SELECT COUNT(*) FROM execution_alert_dead_letters").fetchone()[0]) if self._table_exists(conn, 'execution_alert_dead_letters') else 0
        return WorkerHealth(str(row[0]), row[1], row[2], row[3], int(row[4]), int(row[5]), int(row[6]), pending, dead)

    @staticmethod
    def _table_exists(conn, name: str) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
