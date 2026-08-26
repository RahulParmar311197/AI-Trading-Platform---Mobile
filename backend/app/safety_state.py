from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path


@dataclass
class SafetyState:
    trading_halted: bool = False
    halt_reason: str | None = None
    last_reconciliation_at: datetime | None = None
    halted_at: datetime | None = None


class SafetyStateStore:
    def __init__(self, path: str = "data/safety_state.json") -> None:
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    def save(self, state: SafetyState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trading_halted": state.trading_halted,
            "halt_reason": state.halt_reason,
            "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
            "halted_at": state.halted_at.isoformat() if state.halted_at else None,
        }
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if self.path.exists():
            backup_tmp = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            with backup_tmp.open("wb") as handle:
                handle.write(self.path.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            backup_tmp.replace(self.backup_path)
        tmp.replace(self.path)
        try:
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

    @staticmethod
    def _decode(path: Path) -> SafetyState:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_reconciliation = data.get("last_reconciliation_at")
        raw_halted = data.get("halted_at")
        reconciliation_at = datetime.fromisoformat(raw_reconciliation) if raw_reconciliation else None
        halted_at = datetime.fromisoformat(raw_halted) if raw_halted else None
        return SafetyState(
            bool(data.get("trading_halted", False)),
            data.get("halt_reason"),
            reconciliation_at,
            halted_at,
        )

    def load(self) -> SafetyState:
        if not self.path.exists():
            if self.backup_path.exists():
                try:
                    return self._decode(self.backup_path)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    raise RuntimeError("invalid persisted safety state") from exc
            return SafetyState()
        try:
            return self._decode(self.path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as primary_exc:
            if self.backup_path.exists():
                try:
                    restored = self._decode(self.backup_path)
                    return restored
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as backup_exc:
                    raise RuntimeError("invalid persisted safety state") from backup_exc
            raise RuntimeError("invalid persisted safety state") from primary_exc

    def halt(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("halt reason is required")
        now = datetime.now(timezone.utc)
        state = SafetyState(True, reason, None, now)
        self.save(state)
        return state

    def clear(self, reconciled_at: datetime | None = None) -> SafetyState:
        state = self.load()
        if state.trading_halted:
            if reconciled_at is None:
                raise RuntimeError("post-halt broker reconciliation is required before clearing safety halt")
            if reconciled_at.tzinfo is None:
                raise ValueError("reconciled_at must be timezone-aware")
            if state.halted_at is not None and reconciled_at <= state.halted_at:
                raise RuntimeError("reconciliation must occur after the safety halt")
        cleared_at = datetime.now(timezone.utc)
        state = SafetyState(False, None, reconciled_at or state.last_reconciliation_at or cleared_at, None)
        self.save(state)
        return state
