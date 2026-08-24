from dataclasses import dataclass
from typing import Any

from app.safety_state import SafetyStateStore
from app.session_risk_gate import SessionRiskGate
from app.trading_audit import TradingAuditLog


@dataclass(frozen=True)
class AuthorizationResult:
    allowed: bool
    code: str = "OK"
    reason: str | None = None
    risk_snapshot: Any = None


class ExecutionAuthorization:
    """Single deterministic pre-trade safety gate shared by all execution callers."""

    def __init__(self, safety_store: SafetyStateStore, risk_gate: Any = None,
                 risk_snapshot_provider: Any = None, session_risk_gate: SessionRiskGate | None = None,
                 session_clock: Any = None, audit_log: TradingAuditLog | None = None):
        self.safety_store = safety_store
        self.risk_gate = risk_gate
        self.risk_snapshot_provider = risk_snapshot_provider
        self.session_risk_gate = session_risk_gate
        self.session_clock = session_clock
        self.audit_log = audit_log or TradingAuditLog()

    def _result(self, result: AuthorizationResult, request: Any = None, metadata: dict | None = None) -> AuthorizationResult:
        order_id = getattr(request, "client_order_id", None)
        self.audit_log.record(
            "EXECUTION_AUTHORIZATION",
            reason=result.reason,
            metadata={"client_order_id": order_id, "allowed": result.allowed, "code": result.code, **(metadata or {})},
        )
        return result

    def check_safety(self) -> AuthorizationResult:
        state = self.safety_store.load()
        if state.trading_halted:
            return AuthorizationResult(False, "TRADING_HALTED", state.halt_reason or "safety state active")
        return AuthorizationResult(True)

    def check(self, request: Any) -> AuthorizationResult:
        safety = self.check_safety()
        if not safety.allowed:
            return self._result(safety, request)
        if self.session_risk_gate is not None:
            try:
                if self.session_clock is None:
                    return self._result(AuthorizationResult(False, "SESSION_CLOCK_UNAVAILABLE", "session clock unavailable"), request)
                snapshot = self.session_clock(request)
                result = self.session_risk_gate.evaluate(snapshot.timestamp, snapshot.current_equity, snapshot.realized_daily_pnl)
                if not result.allowed:
                    return self._result(AuthorizationResult(False, "SESSION_RISK_REJECTED", result.reason), request)
            except Exception as exc:
                return self._result(AuthorizationResult(False, "SESSION_RISK_GATE_ERROR", str(exc)), request)
        if self.risk_gate is None:
            return self._result(AuthorizationResult(True), request)
        if self.risk_snapshot_provider is None:
            return self._result(AuthorizationResult(False, "RISK_SNAPSHOT_UNAVAILABLE", "risk snapshot provider unavailable"), request)
        try:
            first_snapshot = self.risk_snapshot_provider(request)
            first_fingerprint = getattr(first_snapshot, "broker_snapshot_fingerprint", None)
            first_decision = self.risk_gate.authorize(request, first_snapshot) if hasattr(self.risk_gate, "authorize") else self.risk_gate.evaluate(request, first_snapshot)
            if not first_decision.allowed:
                return self._result(AuthorizationResult(False, "RISK_REJECTED", first_decision.reason), request, {"broker_snapshot_fingerprint": first_fingerprint})

            # Re-read broker state immediately before reservation/submission. Freshness
            # alone cannot protect against an external order changing exposure after
            # the first risk snapshot was authorized.
            second_snapshot = self.risk_snapshot_provider(request)
            second_fingerprint = getattr(second_snapshot, "broker_snapshot_fingerprint", None)
            if first_fingerprint is None or second_fingerprint is None:
                return self._result(AuthorizationResult(False, "RISK_BROKER_SNAPSHOT_UNVERIFIABLE", "broker snapshot fingerprint unavailable"), request)
            if str(first_fingerprint) != str(second_fingerprint):
                return self._result(AuthorizationResult(False, "RISK_BROKER_SNAPSHOT_CHANGED", "broker state changed during authorization"), request, {"first_broker_snapshot_fingerprint": first_fingerprint, "second_broker_snapshot_fingerprint": second_fingerprint})

            second_decision = self.risk_gate.authorize(request, second_snapshot) if hasattr(self.risk_gate, "authorize") else self.risk_gate.evaluate(request, second_snapshot)
            if not second_decision.allowed:
                return self._result(AuthorizationResult(False, "RISK_REJECTED", second_decision.reason), request, {"broker_snapshot_fingerprint": second_fingerprint})
            return self._result(AuthorizationResult(True, risk_snapshot=second_snapshot), request, {"broker_snapshot_fingerprint": second_fingerprint})
        except Exception as exc:
            return self._result(AuthorizationResult(False, "RISK_GATE_ERROR", str(exc)), request)
