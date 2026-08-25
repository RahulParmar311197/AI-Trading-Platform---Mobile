from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import OrderReconciliationService


@dataclass(frozen=True)
class StartupOrderRecoveryResult:
    ready: bool
    pending_before: int
    pending_after: int
    unresolved_order_ids: tuple[str, ...]
    reason: str


class StartupOrderRecovery:
    """Recover ambiguous local orders before allowing the execution system to become ready."""

    def __init__(self, reconciliation_service: OrderReconciliationService):
        self.reconciliation_service = reconciliation_service

    def run(self, lifecycle: OrderLifecycle, order_ids: Iterable[str] | None = None) -> StartupOrderRecoveryResult:
        ids = list(order_ids) if order_ids is not None else [
            order_id for order_id, order in lifecycle.orders.items()
            if order.status == OrderStatus.PENDING_RECONCILIATION
        ]
        pending_before = len(ids)
        unresolved: list[str] = []
        for order_id in ids:
            result = self.reconciliation_service.reconcile(lifecycle, order_id)
            if not result.resolved or lifecycle.orders[order_id].status == OrderStatus.PENDING_RECONCILIATION:
                unresolved.append(order_id)

        pending_after = sum(
            1 for order in lifecycle.orders.values()
            if order.status == OrderStatus.PENDING_RECONCILIATION
        )
        ready = pending_after == 0
        return StartupOrderRecoveryResult(
            ready=ready,
            pending_before=pending_before,
            pending_after=pending_after,
            unresolved_order_ids=tuple(unresolved),
            reason="all ambiguous orders reconciled" if ready else "unresolved order reconciliation remains",
        )
