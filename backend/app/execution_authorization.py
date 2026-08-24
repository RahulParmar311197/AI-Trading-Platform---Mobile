from dataclasses import dataclass
from typing import Any

from app.safety_state import SafetyStateStore
from app.session_risk_gate import SessionRiskGate


@dataclass(frozen=True)
class AuthorizationResult:
    allowed: bool
    code: str = "OK"
    reason: str | None = None


class ExecutionAuthorization:
    """Single deterministic pre-trade safety gate shared by all execution callers."""

    def __init__(self, safety_store: SafetyStateStore, risk_gate: Any = None,
                 risk_snapshot_provider: Any = None, session_risk_gate: SessionRiskGate | None = None,
                 session_clock: Any = None):
        self.safety_store = safety_store
        self.risk_gate = risk_gate
        self.risk_snapshot_provider = risk_snapshot_provider
        self.session_risk_gate = session_risk_gate
        self.session_clock = session_clock

    def check_safety(self) -> AuthorizationResult:
        state = self.safety_store.load()
        if state.trading_halted:
            return AuthorizationResult(False, "TRADING_HALTED", state.halt_reason or "safety state active")
        return AuthorizationResult(True)

    def check(self, request: Any) -> AuthorizationResult:
        safety = self.check_safety()
        if not safety.allowed:
            return safety
        if self.session_risk_gate is not None:
            try:
                if self.session_clock is None:
                    return AuthorizationResult(False, "SESSION_CLOCK_UNAVAILABLE", "session clock unavailable")
                snapshot = self.session_clock(request)
                result = self.session_risk_gate.evaluate(
                    snapshot.timestamp,
                    snapshot.current_equity,
                    snapshot.realized_daily_pnl,
                )
                if not result.allowed:
                    return AuthorizationResult(False, "SESSION_RISK_REJECTED", result.reason)
            except Exception as exc:
                return AuthorizationResult(False, "SESSION_RISK_GATE_ERROR", str(exc))
        if self.risk_gate is None:
            return AuthorizationResult(True)
        if self.risk_snapshot_provider is None:
            return AuthorizationResult(False, "RISK_SNAPSHOT_UNAVAILABLE", "risk snapshot provider unavailable")
        try:
            snapshot = self.risk_snapshot_provider(request)
            decision = self.risk_gate.authorize(request, snapshot)
            if not decision.allowed:
                return AuthorizationResult(False, "RISK_REJECTED", decision.reason)
        except Exception as exc:
            return AuthorizationResult(False, "RISK_GATE_ERROR", str(exc))
        return AuthorizationResult(True)
