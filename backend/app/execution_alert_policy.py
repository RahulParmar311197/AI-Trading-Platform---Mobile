from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from app.execution_health import ExecutionHealthSnapshot, ExecutionHealthStatus

if TYPE_CHECKING:
    from app.execution_alert_store import ExecutionAlertStore


@dataclass(frozen=True)
class ExecutionAlert:
    severity: ExecutionHealthStatus
    reason_codes: tuple[str, ...]
    fingerprint: str


class ExecutionAlertPolicy:
    """Turns health transitions into deduplicated actionable alerts."""

    def __init__(self, cooldown_seconds: float = 300.0, store: ExecutionAlertStore | None = None) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self.cooldown_seconds = cooldown_seconds
        self.store = store
        self._last_sent: dict[str, float] = {}
        self._last_status: ExecutionHealthStatus | None = None

    @staticmethod
    def _fingerprint(snapshot: ExecutionHealthSnapshot) -> str:
        reasons = ",".join(snapshot.reason_codes)
        return f"{snapshot.status.value}:{reasons}"

    def evaluate(self, snapshot: ExecutionHealthSnapshot, now: float | None = None) -> ExecutionAlert | None:
        if snapshot.status is ExecutionHealthStatus.HEALTHY:
            self._last_status = snapshot.status
            return None
        current = monotonic() if now is None else now
        fingerprint = self._fingerprint(snapshot)
        previous = self._last_sent.get(fingerprint)
        status_escalated = self._last_status is not None and snapshot.status is ExecutionHealthStatus.CRITICAL and self._last_status is not ExecutionHealthStatus.CRITICAL
        if previous is not None and current - previous < self.cooldown_seconds and not status_escalated:
            self._last_status = snapshot.status
            return None
        if self.store is not None:
            from datetime import datetime, timezone

            created = datetime.fromtimestamp(current, tz=timezone.utc) if now is not None else None
            persisted = self.store.record_if_due(
                snapshot.status.value,
                snapshot.reason_codes,
                fingerprint,
                self.cooldown_seconds,
                now=created,
                force=status_escalated,
            )
            if persisted is None:
                self._last_status = snapshot.status
                self._last_sent[fingerprint] = current
                return None
        self._last_sent[fingerprint] = current
        self._last_status = snapshot.status
        return ExecutionAlert(snapshot.status, snapshot.reason_codes, fingerprint)
