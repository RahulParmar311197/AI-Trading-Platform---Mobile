from __future__ import annotations

from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
from app.reconciliation_coordinator import ReconciliationCoordinator
from app.recovery_manager import RecoveryResult, StartupRecoveryManager
from app.safety_state import SafetyStateStore


class BrokerStartupRecovery:
    """Runs startup recovery using the application's selected broker route."""

    def __init__(
        self,
        router: BrokerRouter,
        execution_store: ExecutionStateStore,
        safety_store: SafetyStateStore,
        recovery_manager: StartupRecoveryManager | None = None,
    ) -> None:
        self.router = router
        self.manager = recovery_manager or StartupRecoveryManager(execution_store, safety_store)
        self.execution_store = execution_store

    def run(self, lifecycle: OrderLifecycle, route: str | None = None) -> RecoveryResult:
        """Restore state and provide an authenticated reconciliation result to recovery."""
        selected = self.router.get(route)
        if selected.broker_account_id is None or selected.generation is None or self.router.context_attestor is None:
            return self.manager.startup(lifecycle, lambda: self.router.get_snapshot(route))

        # Load the same durable local execution state that StartupRecoveryManager will restore.
        # This lets the verified reconciliation be computed from the authoritative account-bound
        # route before the manager decides whether persisted safety state may be cleared.
        self.execution_store.load(lifecycle)
        internal_orders = [
            {"client_order_id": order_id, "status": record.status.value, "quantity": record.quantity,
             "filled_quantity": record.filled_quantity}
            for order_id, record in lifecycle.orders.items()
        ]
        internal_positions = [
            {"symbol": position.symbol, "quantity": position.quantity}
            for position in lifecycle.positions.values()
        ]
        snapshot = self.router.get_snapshot(route)
        coordinator = ReconciliationCoordinator(
            engine=self.router.reconciliation_engine,
            route=selected.name,
            account_id=str(selected.broker_account_id),
            route_generation=str(selected.generation),
            context_attestor=self.router.context_attestor,
            generation=self.router._next_reconciliation_generation(selected),
        )
        verified = coordinator.reconcile(
            internal_orders=internal_orders,
            internal_positions=internal_positions,
            broker_snapshot=snapshot,
            broker_ready=True,
        )
        return self.manager.startup(
            lifecycle,
            lambda: snapshot,
            verified_reconciliation=verified,
            active_context=verified.context,
        )
