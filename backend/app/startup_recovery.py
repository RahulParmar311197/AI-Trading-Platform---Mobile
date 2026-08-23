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


class StartupRecoveryCoordinator:
    """Fail-closed startup gate for live execution.

    Recovery must be explicitly completed before live order placement is allowed.
    """

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

    def recover(self, lifecycle, reconcile_order):
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
