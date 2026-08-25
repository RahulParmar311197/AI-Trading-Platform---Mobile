from __future__ import annotations

from app.execution_alert_store import ExecutionAlertRecord, ExecutionAlertStore
from app.execution_health import ExecutionHealth, ExecutionHealthStatus


class ExecutionAlertResolutionService:
    """Automatically resolves only open incidents after a healthy recovery."""

    def __init__(self, health: ExecutionHealth, store: ExecutionAlertStore) -> None:
        self.health = health
        self.store = store

    def evaluate(self) -> list[ExecutionAlertRecord]:
        snapshot = self.health.snapshot()
        if snapshot.status is not ExecutionHealthStatus.HEALTHY:
            return []
        resolved: list[ExecutionAlertRecord] = []
        for record in self.store.recent(200):
            if record.status not in {"OPEN", "ACKNOWLEDGED"}:
                continue
            try:
                resolved.append(self.store.resolve(record.alert_id))
            except (KeyError, ValueError):
                continue
        return resolved
