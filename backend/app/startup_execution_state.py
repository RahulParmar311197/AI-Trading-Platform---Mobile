from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.trading_audit import TradingAuditLog


class StartupExecutionState(str, Enum):
    LOCKED = "LOCKED"
    RECOVERING = "RECOVERING"
    BROKER_RECONCILED = "BROKER_RECONCILED"
    PORTFOLIO_RECONCILED = "PORTFOLIO_RECONCILED"
    RISK_READY = "RISK_READY"
    READY = "READY"
    FAILED = "FAILED"
    HALTED = "HALTED"


@dataclass(frozen=True)
class StartupExecutionStatus:
    state: StartupExecutionState
    reason: str | None = None


class StartupExecutionStateMachine:
    """Single fail-closed state machine for live-execution readiness."""

    _allowed = {
        StartupExecutionState.LOCKED: {StartupExecutionState.RECOVERING, StartupExecutionState.HALTED},
        StartupExecutionState.RECOVERING: {StartupExecutionState.BROKER_RECONCILED, StartupExecutionState.FAILED, StartupExecutionState.HALTED},
        StartupExecutionState.BROKER_RECONCILED: {StartupExecutionState.PORTFOLIO_RECONCILED, StartupExecutionState.FAILED, StartupExecutionState.HALTED},
        StartupExecutionState.PORTFOLIO_RECONCILED: {StartupExecutionState.RISK_READY, StartupExecutionState.FAILED, StartupExecutionState.HALTED},
        StartupExecutionState.RISK_READY: {StartupExecutionState.READY, StartupExecutionState.FAILED, StartupExecutionState.HALTED},
        StartupExecutionState.READY: {StartupExecutionState.HALTED, StartupExecutionState.FAILED},
        StartupExecutionState.FAILED: {StartupExecutionState.RECOVERING, StartupExecutionState.HALTED},
        StartupExecutionState.HALTED: {StartupExecutionState.RECOVERING},
    }

    def __init__(self, audit_log: TradingAuditLog | None = None) -> None:
        self._status = StartupExecutionStatus(StartupExecutionState.LOCKED)
        self.audit_log = audit_log or TradingAuditLog()

    @property
    def state(self) -> StartupExecutionState:
        return self._status.state

    @property
    def status(self) -> StartupExecutionStatus:
        return self._status

    @property
    def execution_allowed(self) -> bool:
        return self.state == StartupExecutionState.READY

    def transition(self, new_state: StartupExecutionState, reason: str | None = None) -> StartupExecutionStatus:
        previous = self.state
        if new_state not in self._allowed[previous]:
            raise RuntimeError(f"invalid startup transition {previous.value}->{new_state.value}")
        if new_state == StartupExecutionState.READY and reason:
            raise RuntimeError("READY cannot carry a failure reason")
        self._status = StartupExecutionStatus(new_state, reason)
        self.audit_log.record(
            "STARTUP_STATE_CHANGE",
            reason=reason,
            from_state=previous.value,
            to_state=new_state.value,
        )
        return self._status

    def fail(self, reason: str) -> StartupExecutionStatus:
        if not reason.strip():
            raise ValueError("failure reason required")
        return self.transition(StartupExecutionState.FAILED, reason)

    def halt(self, reason: str) -> StartupExecutionStatus:
        if not reason.strip():
            raise ValueError("halt reason required")
        return self.transition(StartupExecutionState.HALTED, reason)

    def require_ready(self) -> None:
        if not self.execution_allowed:
            raise RuntimeError(f"live execution locked: startup state={self.state.value}")
