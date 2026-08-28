from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.broker_execution_context import BrokerExecutionContext
from app.broker_snapshot import BrokerSnapshot
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
from app.reconciliation import ReconciliationEngine
from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyStateStore


@dataclass(frozen=True)
class RecoveryResult:
    ready: bool
    state_loaded: bool
    reconciliation: ReconciliationResult | None
    reason: str


class StartupRecoveryManager:
    """Restores local execution state and gates trading on verified broker reconciliation."""

    def __init__(self, execution_store: ExecutionStateStore, safety_store: SafetyStateStore, reconciliation: ReconciliationEngine | None = None) -> None:
        self.execution_store = execution_store
        self.safety_store = safety_store
        self.reconciliation = reconciliation or ReconciliationEngine()
        self._last_result: RecoveryResult | None = None

    def startup(
        self,
        lifecycle: OrderLifecycle,
        broker_snapshot: Callable[[], BrokerSnapshot | tuple[list[dict], list[dict]]],
        *,
        verified_reconciliation: ReconciliationResult | None = None,
        active_context: BrokerExecutionContext | None = None,
    ) -> RecoveryResult:
        """Restore state and only report READY after verified reconciliation clears safety state."""
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
            snapshot = broker_snapshot()
            if isinstance(snapshot, BrokerSnapshot):
                broker_orders, broker_positions = snapshot.orders, snapshot.positions
            else:
                broker_orders, broker_positions = snapshot
            result = self.reconciliation.check(internal_orders, broker_orders, internal_positions, broker_positions)
            if not result.ok:
                self.safety_store.halt("BROKER_STATE_DRIFT")
                recovery = RecoveryResult(False, state_loaded, None, "BROKER_STATE_DRIFT")
            elif persisted.trading_halted:
                self.safety_store.halt(persisted.halt_reason or "PERSISTED_TRADING_HALT")
                recovery = RecoveryResult(False, state_loaded, None, "PERSISTED_TRADING_HALT")
            elif verified_reconciliation is None or active_context is None:
                self.safety_store.halt("VERIFIED_RECONCILIATION_REQUIRED")
                recovery = RecoveryResult(False, state_loaded, None, "VERIFIED_RECONCILIATION_REQUIRED")
            else:
                cleared = self.safety_store.clear(verified_reconciliation, active_context=active_context)
                self.reconciliation.trading_halted = cleared.trading_halted
                recovery = RecoveryResult(True, state_loaded, verified_reconciliation, "RECOVERY_OK")
        except Exception as exc:
            self.reconciliation.trading_halted = True
            self.safety_store.halt(f"RECOVERY_FAILED: {type(exc).__name__}")
            recovery = RecoveryResult(False, False, None, "RECOVERY_FAILED")
        self._last_result = recovery
        return recovery

    def resume_after_verified_reconciliation(self) -> RecoveryResult:
        if self._last_result is None or self._last_result.reconciliation is None:
            raise RuntimeError("startup reconciliation has not completed")
        if not self._last_result.reconciliation.verified:
            raise RuntimeError("startup reconciliation is not verified")
        self.reconciliation.reset_halt()
        state = self.safety_store.load()
        if state.trading_halted:
            raise RuntimeError("cannot resume while safety state remains halted")
        self._last_result = RecoveryResult(True, self._last_result.state_loaded, self._last_result.reconciliation, "RECOVERY_RESUMED")
        return self._last_result

    @property
    def trading_halted(self) -> bool:
        return self.reconciliation.trading_halted
