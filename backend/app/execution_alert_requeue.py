from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class ExecutionAlertRequeueService:
    """Safely returns quarantined notification events to the retry queue."""

    def __init__(self, path: str) -> None:
        self.path = path

    def requeue(self, event_id: int) -> bool:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT event_id FROM execution_alert_dead_letters WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM execution_alert_dead_letters WHERE event_id=?", (event_id,))
            conn.execute("UPDATE execution_alert_deliveries SET delivered_at=NULL,next_attempt_at=?,last_error=NULL WHERE event_id=?", (datetime.now(timezone.utc).isoformat(), event_id))
            conn.commit()
            return True
