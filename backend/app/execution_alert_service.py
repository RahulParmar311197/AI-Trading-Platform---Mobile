from __future__ import annotations

from app.execution_alert_policy import ExecutionAlertPolicy
from app.execution_alert_store import ExecutionAlertRecord, ExecutionAlertStore
from app.execution_health import ExecutionHealth, ExecutionHealthSnapshot


class ExecutionAlertService:
    """Evaluates execution health and persists only policy-approved alerts."""

    def __init__(self, health: ExecutionHealth, policy: ExecutionAlertPolicy, store: ExecutionAlertStore) -> None:
        self.health = health
        self.policy = policy
        self.store = store

    def evaluate(self, now: float | None = None) -> ExecutionAlertRecord | None:
        snapshot = self.health.snapshot()
        return self.evaluate_snapshot(snapshot, now=now)

    def evaluate_snapshot(self, snapshot: ExecutionHealthSnapshot, now: float | None = None) -> ExecutionAlertRecord | None:
        alert = self.policy.evaluate(snapshot, now=now)
        if alert is None:
            return None
        return self.store.record(alert.severity.value, alert.reason_codes, alert.fingerprint)
