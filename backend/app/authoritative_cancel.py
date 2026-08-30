from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker_adapter import BrokerOrderStatus, normalize_broker_update


@dataclass(frozen=True)
class AuthoritativeCancelResult:
    """Result of a cancel request after a post-cancel authoritative broker read."""

    update: Any
    source: str


class AuthoritativeCancelReconciler:
    """Resolve cancel/fill races by treating the post-cancel broker read as truth."""

    TERMINAL = {
        BrokerOrderStatus.CANCELLED.value,
        BrokerOrderStatus.FILLED.value,
        BrokerOrderStatus.REJECTED.value,
    }

    def cancel_and_reconcile(self, broker_router, order) -> AuthoritativeCancelResult:
        broker_order_id = str(order.broker_order_id or "").strip()
        if not broker_order_id:
            raise RuntimeError("broker order ID is required for authoritative cancellation")
        route = str(order.broker_route or "").strip() or None

        # The cancel response only acknowledges the cancel request. It is not
        # authoritative about a concurrent fill that may have won the race.
        broker_router.cancel(
            broker_order_id,
            route=route,
            broker_account_id=order.broker_account_id,
        )

        try:
            raw = broker_router.get_order(broker_order_id, route=route)
        except Exception as exc:
            raise RuntimeError(
                "post-cancel authoritative broker order read failed; reconciliation required"
            ) from exc

        update = normalize_broker_update(raw)
        if str(update.order_id) != broker_order_id:
            raise RuntimeError("post-cancel broker order identity mismatch")
        if update.client_order_id is not None and update.client_order_id != order.client_order_id:
            raise RuntimeError("post-cancel broker client order identity mismatch")
        if update.broker_account_id is not None and str(update.broker_account_id).strip() != str(order.broker_account_id).strip():
            raise RuntimeError("post-cancel broker account identity mismatch")
        if update.broker_route is not None and update.broker_route != order.broker_route:
            raise RuntimeError("post-cancel broker route identity mismatch")
        if update.status not in self.TERMINAL:
            raise RuntimeError("post-cancel broker order is not terminal; reconciliation required")

        return AuthoritativeCancelResult(update=update, source="post_cancel_get_order")
