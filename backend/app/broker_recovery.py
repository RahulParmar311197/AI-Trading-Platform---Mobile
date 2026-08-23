from __future__ import annotations

from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
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

    def run(self, lifecycle: OrderLifecycle, route: str | None = None) -> RecoveryResult:
        return self.manager.startup(lifecycle, lambda: self.router.get_snapshot(route))
