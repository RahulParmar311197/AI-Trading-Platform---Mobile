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
    status: str = "OPEN"
    acknowledged_at: str | None = None
    resolved_at: str | None = None


@dataclass(frozen=True)
class ExecutionAlertPage:
    records: list[ExecutionAlertRecord]
    total: int
    limit: int
    offset: int


class ExecutionAlertStore:
    """Durable SQLite-backed execution alert history and lifecycle."""

    def __init__(self, path: str = "execution_alerts.db") -> None:
        self.path = path
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS execution_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, severity TEXT NOT NULL, reason_codes TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', acknowledged_at TEXT, resolved_at TEXT)""")
            for column, definition in (("status", "TEXT NOT NULL DEFAULT 'OPEN'"), ("acknowledged_at", "TEXT"), ("resolved_at", "TEXT")):
                try:
                    conn.execute(f"ALTER TABLE execution_alerts ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_fingerprint_created ON execution_alerts(fingerprint, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_status ON execution_alerts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_alerts_severity_created ON execution_alerts(severity, created_at DESC)")
            conn.commit()

    @staticmethod
    def _record_from_row(row: tuple[object, ...]) -> ExecutionAlertRecord:
        return ExecutionAlertRecord(int(row[0]), str(row[1]), str(row[2]), tuple(filter(None, str(row[3]).split(","))), str(row[4]), str(row[5] or "OPEN"), str(row[6]) if row[6] else None, str(row[7]) if row[7] else None)

    def record(self, severity: str, reason_codes: tuple[str, ...], fingerprint: str) -> ExecutionAlertRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute("INSERT INTO execution_alerts(created_at,severity,reason_codes,fingerprint,status) VALUES (?,?,?,?, 'OPEN')", (created_at, severity, ",".join(reason_codes), fingerprint))
            conn.commit()
            return ExecutionAlertRecord(int(cursor.lastrowid), created_at, severity, reason_codes, fingerprint)

    def record_if_due(self, severity: str, reason_codes: tuple[str, ...], fingerprint: str, cooldown_seconds: float, *, now: datetime | None = None, force: bool = False) -> ExecutionAlertRecord | None:
        if cooldown_seconds < 0: raise ValueError("cooldown_seconds must be non-negative")
        created_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not force:
                row = conn.execute("SELECT id FROM execution_alerts WHERE fingerprint=? AND julianday(created_at)>=julianday(?)-(?/86400.0) ORDER BY id DESC LIMIT 1", (fingerprint, created_at, float(cooldown_seconds))).fetchone()
                if row is not None: conn.rollback(); return None
            cursor = conn.execute("INSERT INTO execution_alerts(created_at,severity,reason_codes,fingerprint,status) VALUES (?,?,?,?, 'OPEN')", (created_at, severity, ",".join(reason_codes), fingerprint))
            conn.commit()
            return ExecutionAlertRecord(int(cursor.lastrowid), created_at, severity, reason_codes, fingerprint)

    def acknowledge(self, alert_id: int) -> ExecutionAlertRecord: return self._transition(alert_id, "ACKNOWLEDGED")
    def resolve(self, alert_id: int) -> ExecutionAlertRecord: return self._transition(alert_id, "RESOLVED")

    def _transition(self, alert_id: int, target: str) -> ExecutionAlertRecord:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT id,created_at,severity,reason_codes,fingerprint,status,acknowledged_at,resolved_at FROM execution_alerts WHERE id=?", (alert_id,)).fetchone()
            if row is None: raise KeyError(f"execution alert {alert_id} not found")
            current = str(row[5] or "OPEN")
            if target == "ACKNOWLEDGED" and current != "OPEN": raise ValueError(f"cannot acknowledge alert in {current} state")
            if target == "RESOLVED" and current == "RESOLVED": return self._record_from_row(row)
            if target == "RESOLVED": conn.execute("UPDATE execution_alerts SET status='RESOLVED',resolved_at=? WHERE id=?", (now, alert_id))
            else: conn.execute("UPDATE execution_alerts SET status='ACKNOWLEDGED',acknowledged_at=? WHERE id=?", (now, alert_id))
            conn.commit()
            return self._record_from_row(conn.execute("SELECT id,created_at,severity,reason_codes,fingerprint,status,acknowledged_at,resolved_at FROM execution_alerts WHERE id=?", (alert_id,)).fetchone())

    def query(self, *, limit: int = 50, offset: int = 0, severity: str | None = None, status: str | None = None, reason_code: str | None = None, created_after: datetime | None = None, created_before: datetime | None = None) -> ExecutionAlertPage:
        limit = max(1, min(int(limit), 200)); offset = max(0, int(offset))
        clauses: list[str] = []; params: list[object] = []
        if severity: clauses.append("severity=?"); params.append(severity)
        if status: clauses.append("status=?"); params.append(status)
        if reason_code: clauses.append("(',' || reason_codes || ',') LIKE ?"); params.append(f"%,{reason_code},%")
        if created_after: clauses.append("created_at>=?"); params.append(created_after.astimezone(timezone.utc).isoformat())
        if created_before: clauses.append("created_at<=?"); params.append(created_before.astimezone(timezone.utc).isoformat())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with sqlite3.connect(self.path) as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM execution_alerts" + where, params).fetchone()[0])
            rows = conn.execute("SELECT id,created_at,severity,reason_codes,fingerprint,status,acknowledged_at,resolved_at FROM execution_alerts" + where + " ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        return ExecutionAlertPage([self._record_from_row(row) for row in rows], total, limit, offset)

    def recent(self, limit: int = 50) -> list[ExecutionAlertRecord]: return self.query(limit=limit).records
