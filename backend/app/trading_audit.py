from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class TradingAuditEvent:
    event_type: str
    timestamp: str
    reason: str | None = None
    actor: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    metadata: dict[str, Any] | None = None


class TradingAuditLog:
    """Append-only JSONL audit trail for safety-critical trading events."""

    def __init__(self, path: str = "data/trading_audit.jsonl") -> None:
        self.path = Path(path)
        self._lock = Lock()

    def record(self, event_type: str, *, reason: str | None = None, actor: str | None = None,
               from_state: str | None = None, to_state: str | None = None,
               metadata: dict[str, Any] | None = None) -> TradingAuditEvent:
        if not event_type.strip():
            raise ValueError("event_type is required")
        event = TradingAuditEvent(
            event_type=event_type.strip(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            metadata=metadata or {},
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(event), separators=(",", ":"), default=str) + "\n")
                handle.flush()
        return event
