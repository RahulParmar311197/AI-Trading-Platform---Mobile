from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class SafetyState:
    trading_halted: bool = False
    halt_reason: str | None = None
    last_reconciliation_at: datetime | None = None


class SafetyStateStore:
    def __init__(self, path: str = "data/safety_state.json") -> None:
        self.path = Path(path)

    def save(self, state: SafetyState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trading_halted": state.trading_halted,
            "halt_reason": state.halt_reason,
            "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def load(self) -> SafetyState:
        if not self.path.exists():
            return SafetyState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            raw = data.get("last_reconciliation_at")
            timestamp = datetime.fromisoformat(raw) if raw else None
            return SafetyState(bool(data.get("trading_halted", False)), data.get("halt_reason"), timestamp)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid persisted safety state") from exc

    def halt(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("halt reason is required")
        state = SafetyState(True, reason, datetime.now(timezone.utc))
        self.save(state)
        return state

    def clear(self) -> SafetyState:
        state = SafetyState(False, None, datetime.now(timezone.utc))
        self.save(state)
        return state
