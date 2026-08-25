from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class NotificationHealthPolicy:
    stale_after_seconds: int = 30
    pending_threshold: int = 100
    dead_letter_threshold: int = 1

    def evaluate(self, worker_status: str, last_success_at: str | None, pending: int, dead_lettered: int) -> tuple[str, list[str]]:
        reasons: list[str] = []
        if worker_status != "RUNNING":
            reasons.append(f"WORKER_{worker_status}")
        if last_success_at:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success_at)).total_seconds()
                if age > self.stale_after_seconds:
                    reasons.append("STALE_HEARTBEAT")
            except ValueError:
                reasons.append("INVALID_HEARTBEAT")
        else:
            reasons.append("NO_SUCCESSFUL_HEARTBEAT")
        if pending >= self.pending_threshold:
            reasons.append("OUTBOX_BACKLOG")
        if dead_lettered >= self.dead_letter_threshold:
            reasons.append("DEAD_LETTER_EVENTS")
        return ("HEALTHY" if not reasons else "DEGRADED", reasons)
