from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
from app.reconciliation import ReconciliationEngine, ReconciliationResult
from app.safety_state import SafetyStateStore


@dataclass(frozen=True)
class RecoveryResult:
    ready: bool
    state_loaded: bool
    reconciliation: ReconciliationResult | None
    reason: str


class StartupRecoveryManager:
    """Restores local execution state and gates trading on broker reconciliation.

    The broker snapshot callback must return ``(orders, positions)``. Broker I/O
    stays outside this class so adapters can implement their own authentication,
    retries, and transport without coupling recovery to a vendor.
    """

    def __init__(
        self,
        execution_store: ExecutionStateStore,
        safety_store: SafetyStateStore,
        reconciliation: ReconciliationEngine | None = None,
    ) -> None:
        self.execution_store = execution_store
        self.safety_store = safety_store
        self.reconciliation = reconciliation or ReconciliationEngine()
        self._last_result: RecoveryResult | None = None

    def startup(
        self,
        lifecycle: OrderLifecycle,
        broker_snapshot: Callable[[], tuple[list[dict], list[dict]]],
    ) -> RecoveryResult:
        try:
            state_loaded = self.execution_store.load(lifecycle)
            persisted = self.safety_store.load()
            self.reconciliation.trading_halted = persisted.trading_halted
            internal_orders = [
                {"client_order_id": order_id, "status": record.status.value}
                for order_id, record in lifecycle.orders.items()
            ]
            internal_positions = [
                {"symbol": p.symbol, "quantity": p.quantity}
                for p in lifecycle.positions.values()
            ]
            broker_orders, broker_positions = broker_snapshot()
            result = self.reconciliation.check(
                internal_orders,
                broker_orders,
                internal_positions,
                broker_positions,
            )
            if not result.ok:
                self.safety_store.halt("BROKER_STATE_DRIFT")
                recovery = RecoveryResult(False, state_loaded, result, "BROKER_STATE_DRIFT")
            elif persisted.trading_halted:
                self.safety_store.halt(persisted.halt_reason or "PERSISTED_TRADING_HALT")
                recovery = RecoveryResult(False, state_loaded, result, "PERSISTED_TRADING_HALT")
            else:
                self.safety_store.clear()
                recovery = RecoveryResult(True, state_loaded, result, "RECOVERY_OK")
        except Exception as exc:
            self.reconciliation.trading_halted = True
            self.safety_store.halt(f"RECOVERY_FAILED: {type(exc).__name__}")
            recovery = RecoveryResult(False, False, None, "RECOVERY_FAILED")
        self._last_result = recovery
        return recovery

    def resume_after_verified_reconciliation(self) -> RecoveryResult:
        if self._last_result is None or self._last_result.reconciliation is None:
            raise RuntimeError("startup reconciliation has not completed")
        if not self._last_result.reconciliation.ok:
            raise RuntimeError("cannot resume while reconciliation has drift")
        self.reconciliation.reset_halt()
        self.safety_store.clear()
        self._last_result = RecoveryResult(
            True,
            self._last_result.state_loaded,
            self._last_result.reconciliation,
            "RECOVERY_RESUMED",
        )
        return self._last_result

    @property
    def trading_halted(self) -> bool:
        return self.reconciliation.trading_halted
