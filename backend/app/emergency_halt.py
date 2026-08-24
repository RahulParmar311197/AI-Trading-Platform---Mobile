from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.safety_state import SafetyState, SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


@dataclass(frozen=True)
class EmergencyHaltResult:
    halted: bool
    reason: str
    timestamp: datetime


class EmergencyHaltController:
    """Single emergency-stop controller; persistent and fail-closed."""

    def __init__(self, safety_store: SafetyStateStore, startup_state: StartupExecutionStateMachine) -> None:
        self.safety_store = safety_store
        self.startup_state = startup_state

    def halt(self, reason: str) -> EmergencyHaltResult:
        if not reason or not reason.strip():
            raise ValueError("halt reason is required")
        state = self.safety_store.halt(reason.strip())
        if self.startup_state.state != StartupExecutionState.HALTED:
            self.startup_state.halt(reason.strip())
        return EmergencyHaltResult(True, reason.strip(), state.last_reconciliation_at or datetime.now(timezone.utc))

    def is_halted(self) -> bool:
        return self.safety_store.load().trading_halted

    def require_clear(self) -> None:
        state = self.safety_store.load()
        if state.trading_halted:
            raise RuntimeError(f"TRADING_HALTED: {state.halt_reason or 'emergency halt active'}")

    def clear(self) -> None:
        state = self.safety_store.load()
        if state.trading_halted:
            self.safety_store.clear()
        if self.startup_state.state == StartupExecutionState.HALTED:
            self.startup_state.transition(StartupExecutionState.RECOVERING)
