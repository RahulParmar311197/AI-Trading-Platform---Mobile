from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.order_reconciliation import (
    BrokerOrder,
    OrderReconciliationService,
    _coerce_broker_order,
)


@dataclass(frozen=True)
class StartupOrderRecoveryResult:
    ready: bool
    pending_before: int
    pending_after: int
    unresolved_order_ids: tuple[str, ...]
    reason: str


class StartupOrderRecovery:
    """Recover ambiguous local orders before allowing execution to become ready."""

    def __init__(self, reconciliation_service: OrderReconciliationService):
        self.reconciliation_service = reconciliation_service

    def run(self, lifecycle: OrderLifecycle, order_ids: Iterable[str] | None = None) -> StartupOrderRecoveryResult:
        """Run the legacy single-scope recovery path."""
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

    @staticmethod
    def _account_matches(order, account_id: str, route_name: str) -> bool:
        return (
            order.broker_account_id is not None
            and str(order.broker_account_id) == str(account_id)
            and order.broker_route is not None
            and str(order.broker_route) == str(route_name)
        )

    def run_account(
        self,
        lifecycle: OrderLifecycle,
        *,
        route_name: str,
        account_id: str,
        order_ids: Iterable[str] | None = None,
    ) -> StartupOrderRecoveryResult:
        """Recover pending orders against exactly one account-bound broker route."""
        if not route_name.strip():
            raise ValueError("route_name is required")
        if not str(account_id).strip():
            raise ValueError("account_id is required")

        broker = getattr(self.reconciliation_service, "broker", None)
        if broker is None:
            raise RuntimeError("account-scoped startup recovery requires a broker router")
        get_orders = getattr(broker, "get_orders", None)
        if get_orders is None:
            raise RuntimeError("broker router does not support route-scoped order snapshots")

        ids = list(order_ids) if order_ids is not None else [
            order_id for order_id, order in lifecycle.orders.items()
            if order.status == OrderStatus.PENDING_RECONCILIATION
            and self._account_matches(order, str(account_id), route_name)
        ]
        scoped_ids = {
            order_id for order_id in ids
            if order_id in lifecycle.orders
            and self._account_matches(lifecycle.orders[order_id], str(account_id), route_name)
            and lifecycle.orders[order_id].status == OrderStatus.PENDING_RECONCILIATION
        }
        pending_before = len(scoped_ids)

        raw_orders = get_orders(route_name)
        if raw_orders is None:
            raise RuntimeError("authoritative broker order snapshot is unavailable")
        if hasattr(raw_orders, "require_authoritative"):
            raw_orders = raw_orders.require_authoritative()

        broker_orders: list[BrokerOrder] = []
        for raw in raw_orders:
            coerced = _coerce_broker_order(raw)
            if str(coerced.broker_account_id) != str(account_id):
                continue
            if str(coerced.broker_route or "") != route_name:
                continue
            broker_orders.append(coerced)

        result = OrderReconciliationService(lifecycle).reconcile_pending(broker_orders)
        unresolved = {
            order_id for order_id in scoped_ids
            if lifecycle.orders[order_id].status == OrderStatus.PENDING_RECONCILIATION
        }
        unresolved.update(
            event.order_id for event in result.alerts if event.order_id in scoped_ids
        )
        unresolved_ids = tuple(sorted(unresolved))
        ready = not unresolved_ids
        return StartupOrderRecoveryResult(
            ready=ready,
            pending_before=pending_before,
            pending_after=len(unresolved_ids),
            unresolved_order_ids=unresolved_ids,
            reason="all account-scoped ambiguous orders reconciled" if ready else "unresolved account-scoped order reconciliation remains",
        )
