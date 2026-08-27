from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class IncidentSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    ORDER_REJECTED = "order_rejected"
    UNKNOWN_BROKER_ORDER = "unknown_broker_order"
    POSITION_MISMATCH = "position_mismatch"
    KILL_SWITCH = "kill_switch"


@dataclass(frozen=True)
class TradingIncident:
    incident_type: IncidentType
    severity: IncidentSeverity
    message: str
    created_at: datetime
    broker_order_id: str | None = None


class IncidentReporter:
    """Broker-neutral incident sink for logs, audit persistence, metrics, and alerts."""

    def __init__(self, sink: Callable[[TradingIncident], None] | None = None) -> None:
        self.sink = sink
        self.events: list[TradingIncident] = []

    def report(self, incident_type: IncidentType, severity: IncidentSeverity, message: str, broker_order_id: str | None = None) -> TradingIncident:
        incident = TradingIncident(incident_type, severity, message, datetime.now(timezone.utc), broker_order_id)
        self.events.append(incident)
        if self.sink:
            self.sink(incident)
        return incident

    def report_reconciliation_failure(self, message: str, broker_order_id: str | None = None) -> TradingIncident:
        return self.report(IncidentType.RECONCILIATION_MISMATCH, IncidentSeverity.CRITICAL, message, broker_order_id)

    def report_order_rejection(self, message: str, broker_order_id: str | None = None) -> TradingIncident:
        return self.report(IncidentType.ORDER_REJECTED, IncidentSeverity.CRITICAL, message, broker_order_id)

    def report_kill_switch(self, message: str, broker_order_id: str | None = None) -> TradingIncident:
        return self.report(IncidentType.KILL_SWITCH, IncidentSeverity.CRITICAL, message, broker_order_id)
