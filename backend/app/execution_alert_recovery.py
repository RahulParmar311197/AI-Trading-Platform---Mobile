from __future__ import annotations

from app.execution_alert_resolution import ExecutionAlertResolutionService
from app.execution_alert_store import ExecutionAlertRecord


class ExecutionAlertRecoveryCoordinator:
    """Runs recovery resolution after telemetry changes without touching order flow."""

    def __init__(self, resolver: ExecutionAlertResolutionService) -> None:
        self.resolver = resolver

    def evaluate(self) -> list[ExecutionAlertRecord]:
        return self.resolver.evaluate()
