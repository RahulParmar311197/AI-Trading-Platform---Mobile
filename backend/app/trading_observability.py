from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class TradingEvent:
    event_type: str
    timestamp: datetime
    symbol: str | None = None
    client_order_id: str | None = None
    severity: str = "INFO"
    data: dict[str, Any] = field(default_factory=dict)


class TradingAuditLogger:
    """Structured, append-only in-memory event journal with optional stdlib logging."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("ai_trading.audit")
        self._events: list[TradingEvent] = []
        self._lock = Lock()

    def emit(self, event_type: str, *, symbol: str | None = None, client_order_id: str | None = None,
             severity: str = "INFO", data: dict[str, Any] | None = None) -> TradingEvent:
        event = TradingEvent(event_type, datetime.now(timezone.utc), symbol, client_order_id, severity, data or {})
        with self._lock:
            self._events.append(event)
        self.logger.log(getattr(logging, severity.upper(), logging.INFO), json.dumps(asdict(event), default=str, sort_keys=True))
        return event

    def events(self, *, event_type: str | None = None, client_order_id: str | None = None) -> list[TradingEvent]:
        with self._lock:
            result = list(self._events)
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if client_order_id:
            result = [e for e in result if e.client_order_id == client_order_id]
        return result

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
