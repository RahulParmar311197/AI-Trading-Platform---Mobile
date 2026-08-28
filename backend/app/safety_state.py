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
    risk_circuit_blocked: bool = False
    risk_circuit_reason: str | None = None
    risk_circuit_engaged_at: datetime | None = None


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
            "risk_circuit_blocked": state.risk_circuit_blocked,
            "risk_circuit_reason": state.risk_circuit_reason,
            "risk_circuit_engaged_at": state.risk_circuit_engaged_at.isoformat() if state.risk_circuit_engaged_at else None,
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
        risk_engaged_at = data.get("risk_circuit_engaged_at")
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
            bool(data.get("risk_circuit_blocked", False)),
            data.get("risk_circuit_reason"),
            datetime.fromisoformat(risk_engaged_at) if risk_engaged_at else None,
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
        if state.reconciliation_account_id is not None and str(state.reconciliation_account_id) == str(account_id):
            return {
                "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
                "reconciliation_generation": state.reconciliation_generation,
                "broker_snapshot_fingerprint": state.broker_snapshot_fingerprint,
            }
        return None

    def risk_circuit_status(self) -> tuple[bool, str | None]:
        state = self.load()
        return state.risk_circuit_blocked, state.risk_circuit_reason

    def risk_circuit_reset_ready(self) -> bool:
        """Allow reset only after broker reconciliation newer than the circuit engagement."""
        state = self.load()
        if not state.risk_circuit_blocked or state.risk_circuit_engaged_at is None:
            return False
        engaged_at = state.risk_circuit_engaged_at.astimezone(timezone.utc)
        candidates: list[datetime] = []
        if state.last_reconciliation_at is not None:
            candidates.append(state.last_reconciliation_at.astimezone(timezone.utc))
        for record in state.reconciliation_by_account.values():
            raw = record.get("last_reconciliation_at") if isinstance(record, dict) else None
            if raw:
                try:
                    observed = datetime.fromisoformat(str(raw))
                    if observed.tzinfo is not None:
                        candidates.append(observed.astimezone(timezone.utc))
                except ValueError:
                    continue
        return bool(candidates) and max(candidates) > engaged_at

    def engage_risk_circuit(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("risk circuit reason is required")
        state = self.load()
        engaged = SafetyState(
            state.trading_halted,
            state.halt_reason,
            state.last_reconciliation_at,
            state.halted_at,
            state.reconciliation_generation,
            state.reconciliation_account_id,
            state.broker_snapshot_fingerprint,
            dict(state.reconciliation_by_account),
            True,
            reason.strip(),
            datetime.now(timezone.utc),
        )
        self.save(engaged)
        return engaged

    def reset_risk_circuit(self) -> SafetyState:
        state = self.load()
        if state.risk_circuit_blocked and not self.risk_circuit_reset_ready():
            raise RuntimeError("risk circuit reset requires broker reconciliation after circuit engagement")
        reset = SafetyState(
            state.trading_halted,
            state.halt_reason,
            state.last_reconciliation_at,
            state.halted_at,
            state.reconciliation_generation,
            state.reconciliation_account_id,
            state.broker_snapshot_fingerprint,
            dict(state.reconciliation_by_account),
            False,
            None,
            None,
        )
        self.save(reset)
        return reset

    def halt(self, reason: str) -> SafetyState:
        if not reason.strip():
            raise ValueError("halt reason is required")
        state = self.load()
        halted = SafetyState(
            True, reason, None, datetime.now(timezone.utc), None, None, None,
            dict(state.reconciliation_by_account), state.risk_circuit_blocked,
            state.risk_circuit_reason, state.risk_circuit_engaged_at,
        )
        self.save(halted)
        return halted

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
            state.risk_circuit_blocked,
            state.risk_circuit_reason,
            state.risk_circuit_engaged_at,
        )
        self.save(cleared)
        return cleared
