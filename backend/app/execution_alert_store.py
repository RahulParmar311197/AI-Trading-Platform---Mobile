from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3


@dataclass(frozen=True)
class ExecutionAlertRecord:
    alert_id: int
    created_at: str
    severity: str
    reason_codes: tuple[str, ...]
    fingerprint: str


class ExecutionAlertStore:
    """Durable SQLite-backed execution alert history."""

    def __init__(self, path: str = "execution_alerts.db") -> None:
        self.path = path
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS execution_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    reason_codes TEXT NOT NULL,
                    fingerprint TEXT NOT NULL
                )"""
            )
            conn.commit()

    def record(self, severity: str, reason_codes: tuple[str, ...], fingerprint: str) -> ExecutionAlertRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        encoded = ",".join(reason_codes)
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "INSERT INTO execution_alerts(created_at,severity,reason_codes,fingerprint) VALUES (?,?,?,?)",
                (created_at, severity, encoded, fingerprint),
            )
            conn.commit()
            alert_id = int(cursor.lastrowid)
        return ExecutionAlertRecord(alert_id, created_at, severity, reason_codes, fingerprint)

    def recent(self, limit: int = 50) -> list[ExecutionAlertRecord]:
        safe_limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT id,created_at,severity,reason_codes,fingerprint FROM execution_alerts ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [ExecutionAlertRecord(int(row[0]), row[1], row[2], tuple(filter(None, row[3].split(","))), row[4]) for row in rows]
