from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from app.reconciliation_result import ReconciliationResult


@dataclass
class SafetyState:
    trading_halted: bool = False
    halt_reason: str | None = None
    last_reconciliation_at: datetime | None = None
    halted_at: datetime | None = None
    reconciliation_generation: int | None = None
    reconciliation_account_id: str | None = None


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
            "reconciliation_generation": state.reconciliation_generation,
            "reconciliation_account_id": state.reconciliation_account_id,
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
            data.get("reconciliation_generation"),
            data.get("reconciliation_account_id"),
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
                    return self._decode(self.backup_path)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as backup_exc:
                    raise RuntimeError("invalid persisted safety state") from backup_exc
            raise RuntimeError("invalid persisted safety state") from primary_exc

    def halt(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("halt reason is required")
        now = datetime.now(timezone.utc)
        state = SafetyState(True, reason, None, now, None, None)
        self.save(state)
        return state

    def clear(self, reconciliation: ReconciliationResult) -> SafetyState:
        if not isinstance(reconciliation, ReconciliationResult) or not reconciliation.verified:
            raise ValueError("verified reconciliation result is required before clearing safety halt")
        state = self.load()
        reconciled_at = reconciliation.reconciled_at.astimezone(timezone.utc)
        if state.trading_halted:
            if state.halted_at is not None and reconciled_at <= state.halted_at:
                raise RuntimeError("reconciliation must occur after the safety halt")
        state = SafetyState(
            False,
            None,
            reconciled_at,
            None,
            reconciliation.generation,
            reconciliation.account_id,
        )
        self.save(state)
        return state
