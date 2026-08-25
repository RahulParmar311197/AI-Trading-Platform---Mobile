from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from typing import Callable


@dataclass(frozen=True)
class RecoveryAuditEvent:
    event: str
    idempotency_key: str
    client_order_id: str
    status: str
    reason: str | None = None
    broker_order_id: str | None = None
    occurred_at: str = ""

    def to_json(self) -> str:
        value = asdict(self)
        if not value["occurred_at"]:
            value["occurred_at"] = datetime.now(timezone.utc).isoformat()
        return json.dumps(value, sort_keys=True)


class SubmissionRecoveryAuditor:
    """Small injectable audit sink; callers can route events to logs, DB, or telemetry."""

    def __init__(self, sink: Callable[[RecoveryAuditEvent], None] | None = None) -> None:
        self.events: list[RecoveryAuditEvent] = []
        self.sink = sink or self.events.append

    def record(self, *, event: str, idempotency_key: str, client_order_id: str, status: str, reason: str | None = None, broker_order_id: str | None = None) -> RecoveryAuditEvent:
        item = RecoveryAuditEvent(event, idempotency_key, client_order_id, status, reason, broker_order_id, datetime.now(timezone.utc).isoformat())
        self.sink(item)
        return item
