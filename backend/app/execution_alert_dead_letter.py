from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3


@dataclass(frozen=True)
class DeliveryMetrics:
    pending: int
    delivered: int
    dead_lettered: int
    total_attempts: int


class ExecutionAlertDeadLetterStore:
    """Moves permanently undeliverable alert events into a durable quarantine."""

    def __init__(self, path: str) -> None:
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS execution_alert_dead_letters (event_id INTEGER PRIMARY KEY, quarantined_at TEXT NOT NULL, attempts INTEGER NOT NULL, reason TEXT NOT NULL)")
            conn.commit()

    def quarantine(self, event_id: int, attempts: int, reason: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR IGNORE INTO execution_alert_dead_letters(event_id,quarantined_at,attempts,reason) VALUES (?,?,?,?)", (event_id, datetime.now(timezone.utc).isoformat(), attempts, reason[:500]))
            conn.execute("UPDATE execution_alert_deliveries SET next_attempt_at=NULL,last_error=? WHERE event_id=?", (f"DEAD_LETTER: {reason[:450]}", event_id))
            conn.commit()

    def metrics(self) -> DeliveryMetrics:
        with sqlite3.connect(self.path) as conn:
            pending = int(conn.execute("SELECT COUNT(*) FROM execution_alert_deliveries WHERE delivered_at IS NULL AND event_id NOT IN (SELECT event_id FROM execution_alert_dead_letters)").fetchone()[0])
            delivered = int(conn.execute("SELECT COUNT(*) FROM execution_alert_deliveries WHERE delivered_at IS NOT NULL").fetchone()[0])
            dead = int(conn.execute("SELECT COUNT(*) FROM execution_alert_dead_letters").fetchone()[0])
            attempts = int(conn.execute("SELECT COALESCE(SUM(attempts),0) FROM execution_alert_deliveries").fetchone()[0])
        return DeliveryMetrics(pending, delivered, dead, attempts)
