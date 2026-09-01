from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.order_lifecycle import OrderStatus
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine
from app.trading_audit import TradingAuditLog

class RecoveryState(str, Enum):
    LOCKED = "LOCKED"
    RECOVERING = "RECOVERING"
    READY = "READY"
    FAILED = "FAILED"

@dataclass(frozen=True)
class RecoveryResult:
    state: RecoveryState
    unresolved_order_ids: tuple[str, ...] = ()
    reason: str | None = None
    position_mismatches: tuple[str, ...] = ()

class StartupRecoveryCoordinator:
    """Fail-closed startup recovery gate synchronized with live execution state."""
    def __init__(self, execution_state: StartupExecutionStateMachine | None = None, audit_log: TradingAuditLog | None = None):
        self.audit_log = audit_log or (execution_state.audit_log if execution_state else TradingAuditLog())
        self.execution_state = execution_state or StartupExecutionStateMachine(self.audit_log)
        self.state = RecoveryState.LOCKED
        self.last_result: RecoveryResult | None = None

    @property
    def execution_allowed(self) -> bool:
        return self.state == RecoveryState.READY and self.execution_state.execution_allowed

    def begin(self) -> None:
        if self.state == RecoveryState.READY:
            raise RuntimeError("startup recovery already completed")
        self.state = RecoveryState.RECOVERING
        self.last_result = None
        if self.execution_state.state in {StartupExecutionState.LOCKED, StartupExecutionState.FAILED, StartupExecutionState.HALTED}:
            self.execution_state.transition(StartupExecutionState.RECOVERING, "startup recovery started")

    @staticmethod
    def _position_map(positions):
        result = {}
        for raw in positions:
            symbol = str(raw.get("symbol", raw.get("tradingsymbol", ""))).strip().upper()
            if not symbol:
                raise ValueError("broker position is missing symbol")
            side = str(raw.get("side", "")).strip().upper()
            quantity = float(raw.get("quantity", raw.get("net_quantity", raw.get("netQty", 0))) or 0)
            if quantity < 0:
                raise ValueError(f"negative broker position quantity: {symbol}")
            if side in {"SELL", "SHORT"}:
                signed = -quantity
            elif side in {"", "BUY", "LONG"}:
                signed = quantity
            else:
                raise ValueError(f"unknown broker position side: {raw.get('side')}")
            if abs(signed) > 1e-12:
                result[symbol] = result.get(symbol, 0.0) + signed
        return result

    @classmethod
    def compare_positions(cls, local_positions, broker_positions, tolerance=1e-9):
        local = {}
        for symbol, position in local_positions.items():
            side = str(position.side).strip().upper()
            quantity = float(position.quantity)
            if quantity < 0:
                raise ValueError(f"negative local position quantity: {symbol}")
            if side in {"BUY", "LONG"}:
                signed = quantity
            elif side in {"SELL", "SHORT"}:
                signed = -quantity
            else:
                raise ValueError(f"unknown local position side: {position.side}")
            local[str(symbol).upper()] = signed
        broker = cls._position_map(broker_positions)
        return tuple(f"{symbol}: local={local.get(symbol, 0.0)} broker={broker.get(symbol, 0.0)}" for symbol in sorted(set(local) | set(broker)) if abs(local.get(symbol, 0.0) - broker.get(symbol, 0.0)) > tolerance)

    def _fail(self, reason, unresolved=(), mismatches=()):
        self.state = RecoveryState.FAILED
        self.last_result = RecoveryResult(RecoveryState.FAILED, tuple(unresolved), reason, tuple(mismatches))
        if self.execution_state.state not in {StartupExecutionState.FAILED, StartupExecutionState.HALTED}:
            self.execution_state.fail(reason)
        self.audit_log.record("STARTUP_RECOVERY_FAILED", reason=reason, metadata={"unresolved_order_ids": list(unresolved), "position_mismatches": list(mismatches)})
        return self.last_result

    def recover(self, lifecycle, reconcile_order, broker_positions=None, broker_positions_provider=None):
        self.begin(); unresolved = []
        try:
            for order_id, order in lifecycle.orders.items():
                if order.status not in (OrderStatus.SUBMISSION_INTENT, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED): continue
                updated = reconcile_order(order)
                if updated is None or updated.status in (OrderStatus.SUBMISSION_INTENT, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED): unresolved.append(order_id)
            if unresolved: return self._fail("unresolved orders", unresolved)
            if broker_positions_provider is not None: broker_positions = broker_positions_provider()
            if broker_positions is None: return self._fail("broker position snapshot unavailable")
            mismatches = self.compare_positions(lifecycle.positions, broker_positions)
            if mismatches: return self._fail("position reconciliation mismatch", mismatches=mismatches)
            self.execution_state.transition(StartupExecutionState.BROKER_RECONCILED, "broker state reconciled")
            self.execution_state.transition(StartupExecutionState.PORTFOLIO_RECONCILED, "portfolio matches broker")
            self.execution_state.transition(StartupExecutionState.RISK_READY, "startup recovery checks passed")
            self.execution_state.transition(StartupExecutionState.READY)
            self.state = RecoveryState.READY; self.last_result = RecoveryResult(RecoveryState.READY)
            self.audit_log.record("STARTUP_RECOVERY_READY", metadata={"state": self.execution_state.state.value})
            return self.last_result
        except Exception as exc: return self._fail(str(exc), unresolved)

    def require_execution_ready(self) -> None:
        if not self.execution_allowed: raise RuntimeError(f"live execution locked: recovery state={self.state.value}, execution state={self.execution_state.state.value}")
