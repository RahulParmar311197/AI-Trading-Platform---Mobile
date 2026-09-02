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
    _LOCAL_RECONCILIABLE_STATUSES = {
        OrderStatus.SUBMISSION_INTENT,
        OrderStatus.SUBMITTED,
        OrderStatus.OPEN,
        OrderStatus.PARTIALLY_FILLED,
    }

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
        seen_symbols = set()
        for raw in positions:
            symbol = str(raw.get("symbol", raw.get("tradingsymbol", ""))).strip().upper()
            if not symbol:
                raise ValueError("broker position is missing symbol")
            if symbol in seen_symbols:
                raise ValueError(f"duplicate broker position symbol: {symbol}")
            seen_symbols.add(symbol)
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
                result[symbol] = signed
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

    @staticmethod
    def _broker_order_id(raw):
        if not isinstance(raw, dict):
            raise ValueError("broker order record is invalid")
        value = raw.get("broker_order_id")
        if value is None:
            value = raw.get("order_id")
        identity = str(value or "").strip()
        if not identity:
            raise ValueError("broker order is missing broker_order_id")
        return identity

    @classmethod
    def _local_reconciled_broker_order_ids(cls, lifecycle):
        ids = set()
        for order in lifecycle.orders.values():
            if order.status not in cls._LOCAL_RECONCILIABLE_STATUSES:
                continue
            broker_order_id = str(order.broker_order_id or "").strip()
            if not broker_order_id:
                raise ValueError(f"live local order is missing broker_order_id: {order.order_id}")
            if broker_order_id in ids:
                raise ValueError(f"duplicate local broker_order_id: {broker_order_id}")
            ids.add(broker_order_id)
        return ids

    @classmethod
    def compare_live_orders(cls, lifecycle, broker_orders):
        """Return broker-only live orders; fail closed on ambiguous broker identities."""
        if not isinstance(broker_orders, list):
            raise ValueError("broker order snapshot is invalid")
        local_ids = cls._local_reconciled_broker_order_ids(lifecycle)
        broker_ids = set()
        broker_only = []
        for raw in broker_orders:
            broker_id = cls._broker_order_id(raw)
            if broker_id in broker_ids:
                raise ValueError(f"duplicate broker order identity: {broker_id}")
            broker_ids.add(broker_id)
            status = str(raw.get("status", "")).strip().upper()
            if status in {"NEW", "OPEN", "PENDING", "PARTIALLY_FILLED", "SUBMITTED", "TRANSIT", "VALIDATION PENDING", "OPEN PENDING", "TRIGGER PENDING", "CANCEL PENDING", "MODIFY PENDING"} and broker_id not in local_ids:
                broker_only.append(broker_id)
        return tuple(sorted(broker_only))

    def _fail(self, reason, unresolved=(), mismatches=()):
        self.state = RecoveryState.FAILED
        self.last_result = RecoveryResult(RecoveryState.FAILED, tuple(unresolved), reason, tuple(mismatches))
        if self.execution_state.state not in {StartupExecutionState.FAILED, StartupExecutionState.HALTED}:
            self.execution_state.fail(reason)
        self.audit_log.record("STARTUP_RECOVERY_FAILED", reason=reason, metadata={"unresolved_order_ids": list(unresolved), "position_mismatches": list(mismatches)})
        return self.last_result

    def recover(self, lifecycle, reconcile_order, broker_positions=None, broker_positions_provider=None, broker_orders=None, broker_orders_provider=None):
        self.begin(); unresolved = []
        try:
            for order_id, order in lifecycle.orders.items():
                if order.status not in self._LOCAL_RECONCILIABLE_STATUSES:
                    continue
                updated = reconcile_order(order)
                if updated is None or updated.status in self._LOCAL_RECONCILIABLE_STATUSES:
                    unresolved.append(order_id)
            if unresolved:
                return self._fail("unresolved orders", unresolved)
            if broker_orders_provider is not None:
                broker_orders = broker_orders_provider()
            if broker_orders is not None:
                broker_only = self.compare_live_orders(lifecycle, broker_orders)
                if broker_only:
                    return self._fail("broker-only live orders", unresolved=broker_only)
            if broker_positions_provider is not None:
                broker_positions = broker_positions_provider()
            if broker_positions is None:
                return self._fail("broker position snapshot unavailable")
            mismatches = self.compare_positions(lifecycle.positions, broker_positions)
            if mismatches:
                return self._fail("position reconciliation mismatch", mismatches=mismatches)
            self.execution_state.transition(StartupExecutionState.BROKER_RECONCILED, "broker state reconciled")
            self.execution_state.transition(StartupExecutionState.PORTFOLIO_RECONCILED, "portfolio matches broker")
            self.execution_state.transition(StartupExecutionState.RISK_READY, "startup recovery checks passed")
            self.execution_state.transition(StartupExecutionState.READY)
            self.state = RecoveryState.READY; self.last_result = RecoveryResult(RecoveryState.READY)
            self.audit_log.record("STARTUP_RECOVERY_READY", metadata={"state": self.execution_state.state.value})
            return self.last_result
        except Exception as exc:
            return self._fail(str(exc), unresolved)

    def require_execution_ready(self) -> None:
        if not self.execution_allowed:
            raise RuntimeError(f"live execution locked: recovery state={self.state.value}, execution state={self.execution_state.state.value}")
