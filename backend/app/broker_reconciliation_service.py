from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.broker_router import BrokerRouter
from app.reconciliation_result import ReconciliationResult


@dataclass(frozen=True)
class ReconciliationConfig:
    route: str
    account_id: str
    generation: int


class BrokerReconciliationService:
    """Single production boundary that can produce an unlockable reconciliation result."""

    def __init__(
        self,
        router: BrokerRouter,
        config: ReconciliationConfig,
        unresolved_submission_intents: Callable[[], int] | None = None,
    ) -> None:
        self.router = router
        self.config = config
        self._unresolved_submission_intents = unresolved_submission_intents or (lambda: 0)

    def reconcile(self) -> ReconciliationResult:
        with self.router.route_lifecycle_lock():
            route = self.router.get(self.config.route)
            if route.broker_account_id is not None and str(route.broker_account_id) != str(self.config.account_id):
                raise RuntimeError("reconciliation account does not match broker route")
            if route.generation is not None and str(route.generation) != str(self.config.generation):
                raise RuntimeError("reconciliation generation does not match broker route")

            account = route.adapter.get_account()
            if not isinstance(account, dict):
                raise RuntimeError("broker account snapshot is invalid")
            healthy = account.get("healthy") is True
            authenticated = account.get("authenticated") is True
            if not healthy or not authenticated:
                raise RuntimeError("broker account is not ready for reconciliation")

            orders = route.adapter.get_orders() if hasattr(route.adapter, "get_orders") else None
            if orders is None or not isinstance(orders, list):
                raise RuntimeError("broker open-order snapshot is unavailable")
            positions = route.adapter.get_positions()
            if not isinstance(positions, list):
                raise RuntimeError("broker position snapshot is unavailable")

            unresolved = int(self._unresolved_submission_intents())
            if unresolved < 0:
                raise RuntimeError("unresolved submission-intent count is invalid")
            if unresolved != 0:
                raise RuntimeError("unresolved broker submission intents remain")

            return ReconciliationResult.from_verified_state(
                account_id=self.config.account_id,
                generation=self.config.generation,
                reconciled_at=datetime.now(timezone.utc),
                open_orders_reconciled=True,
                positions_reconciled=True,
                submission_intents_resolved=0,
                broker_ready=True,
            )
