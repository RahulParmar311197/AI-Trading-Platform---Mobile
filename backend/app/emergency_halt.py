from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.safety_state import SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine
from app.trading_audit import TradingAuditLog


@dataclass(frozen=True)
class EmergencyHaltResult:
    halted: bool
    reason: str
    timestamp: datetime


class EmergencyHaltController:
    """Single emergency-stop controller; persistent, audited and fail-closed."""

    def __init__(self, safety_store: SafetyStateStore, startup_state: StartupExecutionStateMachine, audit_log: TradingAuditLog | None = None) -> None:
        self.safety_store = safety_store
        self.startup_state = startup_state
        self.audit_log = audit_log or TradingAuditLog()

    def halt(self, reason: str, actor: str | None = None) -> EmergencyHaltResult:
        if not reason or not reason.strip():
            raise ValueError("halt reason is required")
        before = self.startup_state.state.value
        state = self.safety_store.halt(reason.strip())
        if self.startup_state.state != StartupExecutionState.HALTED:
            self.startup_state.halt(reason.strip())
        timestamp = state.last_reconciliation_at or datetime.now(timezone.utc)
        self.audit_log.record("EMERGENCY_HALT", reason=reason.strip(), actor=actor, from_state=before, to_state=StartupExecutionState.HALTED.value)
        return EmergencyHaltResult(True, reason.strip(), timestamp)

    def is_halted(self) -> bool:
        return self.safety_store.load().trading_halted

    def require_clear(self) -> None:
        state = self.safety_store.load()
        if state.trading_halted:
            raise RuntimeError(f"TRADING_HALTED: {state.halt_reason or 'emergency halt active'}")

    def clear(self, actor: str | None = None) -> None:
        state = self.safety_store.load()
        if state.trading_halted:
            self.safety_store.clear()
        before = self.startup_state.state.value
        if self.startup_state.state == StartupExecutionState.HALTED:
            self.startup_state.transition(StartupExecutionState.RECOVERING)
        self.audit_log.record("EMERGENCY_CLEAR", actor=actor, from_state=before, to_state=self.startup_state.state.value)
