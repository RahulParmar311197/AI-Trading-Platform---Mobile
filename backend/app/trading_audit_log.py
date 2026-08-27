from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Any

from app.trading_incidents import TradingIncident


class TradingAuditLog:
    """Append-only durable JSONL audit sink for trading incidents/events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def append_incident(self, incident: TradingIncident) -> None:
        self.append({"event_type": "trading_incident", **_jsonable(asdict(incident))})

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(_jsonable(event), separators=(",", ":"), sort_keys=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value
