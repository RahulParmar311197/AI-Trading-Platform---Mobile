from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.order_lifecycle import OrderStatus


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
    """Fail-closed startup gate for live execution."""

    def __init__(self):
        self.state = RecoveryState.LOCKED
        self.last_result: RecoveryResult | None = None

    @property
    def execution_allowed(self) -> bool:
        return self.state == RecoveryState.READY

    def begin(self) -> None:
        if self.state == RecoveryState.READY:
            raise RuntimeError("startup recovery already completed")
        self.state = RecoveryState.RECOVERING
        self.last_result = None

    @staticmethod
    def _position_map(positions):
        result = {}
        for raw in positions:
            symbol = str(raw.get("symbol", raw.get("tradingsymbol", ""))).strip().upper()
            if not symbol:
                raise ValueError("broker position is missing symbol")
            side = str(raw.get("side", "")).strip().upper()
            quantity = raw.get("quantity", raw.get("net_quantity", raw.get("netQty", 0)))
            quantity = float(quantity or 0)
            if quantity < 0:
                raise ValueError(f"negative broker position quantity: {symbol}")
            if side in {"SELL", "SHORT"}:
                signed = -quantity
            elif side in {"BUY", "LONG"}:
                signed = quantity
            else:
                signed = quantity if quantity >= 0 else -quantity
            if abs(signed) > 1e-12:
                result[symbol] = result.get(symbol, 0.0) + signed
        return result

    @classmethod
    def compare_positions(cls, local_positions, broker_positions, tolerance=1e-9):
        local = {}
        for symbol, position in local_positions.items():
            quantity = float(position.quantity)
            local[str(symbol).upper()] = quantity if str(position.side).upper() == "BUY" else -quantity
        broker = cls._position_map(broker_positions)
        mismatches = []
        for symbol in sorted(set(local) | set(broker)):
            if abs(local.get(symbol, 0.0) - broker.get(symbol, 0.0)) > tolerance:
                mismatches.append(f"{symbol}: local={local.get(symbol, 0.0)} broker={broker.get(symbol, 0.0)}")
        return tuple(mismatches)

    def recover(self, lifecycle, reconcile_order, broker_positions=None):
        self.begin()
        unresolved: list[str] = []
        try:
            for order_id, order in lifecycle.orders.items():
                if order.status not in (OrderStatus.SUBMISSION_INTENT, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                    continue
                updated = reconcile_order(order)
                if updated is None or updated.status in (OrderStatus.SUBMISSION_INTENT, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                    unresolved.append(order_id)
            if unresolved:
                self.state = RecoveryState.FAILED
                self.last_result = RecoveryResult(RecoveryState.FAILED, tuple(unresolved), "unresolved orders")
                return self.last_result
            if broker_positions is not None:
                mismatches = self.compare_positions(lifecycle.positions, broker_positions)
                if mismatches:
                    self.state = RecoveryState.FAILED
                    self.last_result = RecoveryResult(RecoveryState.FAILED, (), "position reconciliation mismatch", mismatches)
                    return self.last_result
            self.state = RecoveryState.READY
            self.last_result = RecoveryResult(RecoveryState.READY)
            return self.last_result
        except Exception as exc:
            self.state = RecoveryState.FAILED
            self.last_result = RecoveryResult(RecoveryState.FAILED, tuple(unresolved), str(exc))
            raise

    def require_execution_ready(self) -> None:
        if not self.execution_allowed:
            raise RuntimeError(f"live execution locked: recovery state={self.state.value}")
