from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from app.broker_execution_context import BrokerExecutionContext
from app.reconciliation_result import ReconciliationResult


@dataclass
class SafetyState:
    trading_halted: bool = False
    halt_reason: str | None = None
    last_reconciliation_at: datetime | None = None
    halted_at: datetime | None = None
    reconciliation_generation: int | None = None
    reconciliation_account_id: str | None = None
    broker_snapshot_fingerprint: str | None = None
    reconciliation_by_account: dict[str, dict[str, object]] = field(default_factory=dict)


class SafetyStateStore:
    def __init__(self, path: str = "data/safety_state.json") -> None:
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    @staticmethod
    def _context_record(reconciliation: ReconciliationResult, context: BrokerExecutionContext) -> dict[str, object]:
        return {
            "last_reconciliation_at": reconciliation.reconciled_at.astimezone(timezone.utc).isoformat(),
            "reconciliation_generation": context.generation,
            "broker_route": context.broker_route,
            "route_generation": context.route_generation,
            "broker_snapshot_fingerprint": context.snapshot_fingerprint,
        }

    def save(self, state: SafetyState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trading_halted": state.trading_halted,
            "halt_reason": state.halt_reason,
            "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
            "halted_at": state.halted_at.isoformat() if state.halted_at else None,
            "reconciliation_generation": state.reconciliation_generation,
            "reconciliation_account_id": state.reconciliation_account_id,
            "broker_snapshot_fingerprint": state.broker_snapshot_fingerprint,
            "reconciliation_by_account": state.reconciliation_by_account,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            handle.write(json.dumps(payload, indent=2).encode())
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
            fd = os.open(self.path.parent, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
        except OSError:
            pass

    @staticmethod
    def _decode(path: Path) -> SafetyState:
        data = json.loads(path.read_text(encoding="utf-8"))
        reconciled_at = data.get("last_reconciliation_at")
        halted_at = data.get("halted_at")
        by_account = data.get("reconciliation_by_account") or {}
        if not isinstance(by_account, dict):
            raise ValueError("invalid account reconciliation state")
        return SafetyState(
            bool(data.get("trading_halted", False)),
            data.get("halt_reason"),
            datetime.fromisoformat(reconciled_at) if reconciled_at else None,
            datetime.fromisoformat(halted_at) if halted_at else None,
            data.get("reconciliation_generation"),
            data.get("reconciliation_account_id"),
            data.get("broker_snapshot_fingerprint"),
            by_account,
        )

    def load(self) -> SafetyState:
        try:
            if not self.path.exists():
                return self._decode(self.backup_path) if self.backup_path.exists() else SafetyState()
            return self._decode(self.path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            try:
                return self._decode(self.backup_path)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as backup_exc:
                raise RuntimeError("invalid persisted safety state") from backup_exc

    def account_reconciliation(self, account_id: str) -> dict[str, object] | None:
        state = self.load()
        record = state.reconciliation_by_account.get(str(account_id))
        if record is not None:
            return dict(record)
        # Backward-compatible read of the legacy single-account state.
        if state.reconciliation_account_id is not None and str(state.reconciliation_account_id) == str(account_id):
            return {
                "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
                "reconciliation_generation": state.reconciliation_generation,
                "broker_snapshot_fingerprint": state.broker_snapshot_fingerprint,
            }
        return None

    def halt(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("halt reason is required")
        state = SafetyState(True, reason, None, datetime.now(timezone.utc), None, None, None, {})
        self.save(state)
        return state

    def clear(self, reconciliation: ReconciliationResult, *, active_context: BrokerExecutionContext) -> SafetyState:
        if not isinstance(reconciliation, ReconciliationResult) or not reconciliation.verified:
            raise ValueError("verified reconciliation result is required before clearing safety halt")
        if not isinstance(active_context, BrokerExecutionContext):
            raise ValueError("active broker execution context is required")
        if reconciliation.context.canonical_key != active_context.canonical_key:
            raise RuntimeError("reconciliation does not match active broker execution context")

        state = self.load()
        at = reconciliation.reconciled_at.astimezone(timezone.utc)
        if state.trading_halted and state.halted_at is not None and at <= state.halted_at:
            raise RuntimeError("reconciliation must occur after the safety halt")
        account_id = str(active_context.account_id)
        account_states = dict(state.reconciliation_by_account)
        account_states[account_id] = self._context_record(reconciliation, active_context)
        cleared = SafetyState(
            False,
            None,
            at,
            None,
            active_context.generation,
            active_context.account_id,
            active_context.snapshot_fingerprint,
            account_states,
        )
        self.save(cleared)
        return cleared
