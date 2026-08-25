from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

from app.execution_alert_dispatcher import ExecutionAlertDispatcher


class ExecutionAlertOutboxWorker:
    """Bounded worker tick for retrying undelivered alert events."""

    def __init__(self, dispatcher: ExecutionAlertDispatcher, max_attempts: int = 8, base_delay_seconds: float = 2.0) -> None:
        if max_attempts < 1 or base_delay_seconds < 0:
            raise ValueError("invalid retry configuration")
        self.dispatcher = dispatcher
        self.path = dispatcher.path
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def _due_events(self, limit: int) -> list[int]:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("""SELECT e.id FROM execution_alert_events e LEFT JOIN execution_alert_deliveries d ON d.event_id=e.id WHERE d.delivered_at IS NULL AND COALESCE(d.attempts,0) < ? AND (d.next_attempt_at IS NULL OR d.next_attempt_at <= ?) AND (d.lease_token IS NULL OR d.lease_expires_at IS NULL OR d.lease_expires_at <= ?) ORDER BY e.id ASC LIMIT ?""", (self.max_attempts, now, now, max(1, min(limit, 100)))).fetchall()
        return [int(row[0]) for row in rows]

    def run_once(self, limit: int = 25) -> list:
        results = []
        for event_id in self._due_events(limit):
            result = self.dispatcher.dispatch_once(event_id)
            results.append(result)
            if not result.delivered:
                delay = self.base_delay_seconds * (2 ** max(0, result.attempts - 1))
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=min(delay, 3600))).isoformat()
                with sqlite3.connect(self.path) as conn:
                    conn.execute("UPDATE execution_alert_deliveries SET next_attempt_at=? WHERE event_id=? AND delivered_at IS NULL AND (lease_token IS NULL OR lease_expires_at <= ?)", (retry_at, event_id, datetime.now(timezone.utc).isoformat()))
                    conn.commit()
        return results
