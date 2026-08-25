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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_execution_alerts_fingerprint_created "
                "ON execution_alerts(fingerprint, created_at DESC)"
            )
            conn.commit()

    @staticmethod
    def _record_from_row(row: tuple[object, ...]) -> ExecutionAlertRecord:
        return ExecutionAlertRecord(
            int(row[0]),
            str(row[1]),
            str(row[2]),
            tuple(filter(None, str(row[3]).split(","))),
            str(row[4]),
        )

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

    def record_if_due(
        self,
        severity: str,
        reason_codes: tuple[str, ...],
        fingerprint: str,
        cooldown_seconds: float,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> ExecutionAlertRecord | None:
        """Atomically persist an alert unless the same fingerprint is still in cooldown."""
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        created_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        encoded = ",".join(reason_codes)
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not force:
                row = conn.execute(
                    """SELECT id,created_at,severity,reason_codes,fingerprint
                       FROM execution_alerts
                       WHERE fingerprint = ?
                         AND julianday(created_at) >= julianday(?) - (? / 86400.0)
                       ORDER BY id DESC LIMIT 1""",
                    (fingerprint, created_at, float(cooldown_seconds)),
                ).fetchone()
                if row is not None:
                    conn.rollback()
                    return None
            cursor = conn.execute(
                "INSERT INTO execution_alerts(created_at,severity,reason_codes,fingerprint) VALUES (?,?,?,?)",
                (created_at, severity, encoded, fingerprint),
            )
            conn.commit()
            return ExecutionAlertRecord(int(cursor.lastrowid), created_at, severity, reason_codes, fingerprint)

    def recent(self, limit: int = 50) -> list[ExecutionAlertRecord]:
        safe_limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT id,created_at,severity,reason_codes,fingerprint FROM execution_alerts ORDER BY id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]
