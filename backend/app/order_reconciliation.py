from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.order_lifecycle import OrderLifecycle, OrderStatus


class ReconciliationAction(str, Enum):
    NOOP = "NOOP"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ALERT = "ALERT"
    PENDING = "PENDING"


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float
    status: OrderStatus
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    client_order_id: str | None = None
    broker_account_id: int | None = None
    broker_route: str | None = None


@dataclass(frozen=True)
class ReconciliationEvent:
    order_id: str
    action: ReconciliationAction
    reason: str


class AmbiguousBrokerOrderIdentity(RuntimeError):
    """Raised when one broker update can safely match more than one local order."""


class OrderReconciler:
    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle

    def _find_local(self, remote: BrokerOrder):
        candidates = []
        direct = self.lifecycle.orders.get(remote.order_id)
        if direct is not None:
            candidates.append(direct)
        for order in self.lifecycle.orders.values():
            if order.broker_order_id == remote.order_id or (
                remote.client_order_id and order.order_id == remote.client_order_id
            ):
                if order not in candidates:
                    candidates.append(order)

        valid = [candidate for candidate in candidates if self._validate_account_identity(candidate, remote) is None]
        if len(valid) > 1:
            raise AmbiguousBrokerOrderIdentity(
                f"multiple local orders match broker order {remote.order_id}"
            )
        if valid:
            return valid[0]
        return candidates[0] if candidates else None

    @staticmethod
    def _validate_account_identity(local, remote: BrokerOrder):
        if local.broker_account_id is not None:
            if remote.broker_account_id is None:
                return "BROKER_ACCOUNT_ID_MISSING"
            if int(local.broker_account_id) != int(remote.broker_account_id):
                return "BROKER_ACCOUNT_ID_MISMATCH"
        if local.broker_route is not None:
            if not remote.broker_route:
                return "BROKER_ROUTE_MISSING"
            if str(local.broker_route) != str(remote.broker_route):
                return "BROKER_ROUTE_MISMATCH"
        return None

    @classmethod
    def _validate_identity(cls, local, remote: BrokerOrder):
        account_error = cls._validate_account_identity(local, remote)
        if account_error:
            return account_error
        if local.symbol.upper() != remote.symbol.upper():
            return "BROKER_SYMBOL_MISMATCH"
        if local.side.upper() != remote.side.upper():
            return "BROKER_SIDE_MISMATCH"
        if abs(float(local.quantity) - float(remote.quantity)) > 1e-9:
            return "BROKER_QUANTITY_MISMATCH"
        if remote.client_order_id and local.order_id != remote.client_order_id:
            return "BROKER_CLIENT_ORDER_ID_MISMATCH"
        return None

    def reconcile(self, broker_orders: list[BrokerOrder]) -> list[ReconciliationEvent]:
        events = []
        seen = set()
        for remote in broker_orders:
            if remote.order_id in seen:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, "DUPLICATE_BROKER_UPDATE"))
                continue
            seen.add(remote.order_id)
            try:
                local = self._find_local(remote)
            except AmbiguousBrokerOrderIdentity as exc:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, f"AMBIGUOUS_BROKER_ORDER_IDENTITY:{exc}"))
                continue
            if local is None:
                local_id = remote.client_order_id or remote.order_id
                if local_id in self.lifecycle.orders:
                    events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, "BROKER_CLIENT_ORDER_ID_COLLISION"))
                    continue
                if remote.broker_account_id is None or not remote.broker_route:
                    events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, "BROKER_ACCOUNT_IDENTITY_MISSING"))
                    continue
                try:
                    self.lifecycle.create(local_id, remote.symbol, remote.side, remote.quantity, broker_account_id=remote.broker_account_id, broker_route=remote.broker_route)
                    local = self.lifecycle.orders[local_id]
                    local.broker_order_id = remote.order_id
                    self.lifecycle.transition(local_id, remote.status, remote.filled_quantity, remote.average_fill_price)
                except (TypeError, ValueError, RuntimeError) as exc:
                    events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, f"BROKER_UPDATE_REJECTED:{exc}"))
                    continue
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.CREATE, "MISSING_LOCAL_ORDER"))
                continue

            identity_error = self._validate_identity(local, remote)
            if identity_error:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, identity_error))
                continue
            if local.broker_order_id is None:
                local.broker_order_id = remote.order_id
            current = (local.status, local.filled_quantity, local.average_fill_price)
            incoming = (remote.status, remote.filled_quantity, remote.average_fill_price)
            if current == incoming:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.NOOP, "ALREADY_IN_SYNC"))
                continue
            try:
                self.lifecycle.transition(local.order_id, remote.status, remote.filled_quantity, remote.average_fill_price)
            except (TypeError, ValueError, RuntimeError) as exc:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, f"BROKER_UPDATE_REJECTED:{exc}"))
                continue
            events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.UPDATE, "LOCAL_STATE_RECONCILED"))
        return events

    def reconcile_pending(self, broker_orders: list[BrokerOrder]) -> list[ReconciliationEvent]:
        pending = {o.order_id for o in self.lifecycle.orders.values() if o.status == OrderStatus.PENDING_RECONCILIATION}
        if not pending:
            return []
        events = []
        matched = set()
        for remote in broker_orders:
            try:
                local = self._find_local(remote)
            except AmbiguousBrokerOrderIdentity as exc:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, f"AMBIGUOUS_BROKER_ORDER_IDENTITY:{exc}"))
                continue
            if local is None or local.order_id not in pending:
                continue
            matched.add(local.order_id)
            identity_error = self._validate_identity(local, remote)
            if identity_error:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, identity_error))
                continue
            try:
                self.lifecycle.transition(local.order_id, remote.status, remote.filled_quantity, remote.average_fill_price)
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.UPDATE, "PENDING_ORDER_RESOLVED"))
            except (TypeError, ValueError, RuntimeError) as exc:
                events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, f"PENDING_RESOLUTION_REJECTED:{exc}"))
        for order_id in sorted(pending - matched):
            events.append(ReconciliationEvent(order_id, ReconciliationAction.PENDING, "BROKER_ORDER_NOT_FOUND"))
        return events


# Backwards-compatible application-service import surface.  The implementation
# lives here so callers importing from app.order_reconciliation keep one engine.
@dataclass(frozen=True)
class OrderReconciliationResult:
    events: tuple[ReconciliationEvent, ...]

    @property
    def alerts(self) -> tuple[ReconciliationEvent, ...]:
        return tuple(e for e in self.events if e.action is ReconciliationAction.ALERT)

    @property
    def changed(self) -> bool:
        return any(e.action in (ReconciliationAction.CREATE, ReconciliationAction.UPDATE) for e in self.events)


class OrderReconciliationService:
    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle
        self.reconciler = OrderReconciler(lifecycle)

    def reconcile(self, broker_orders):
        return OrderReconciliationResult(tuple(self.reconciler.reconcile(list(broker_orders))))

    def reconcile_pending(self, broker_orders):
        return OrderReconciliationResult(tuple(self.reconciler.reconcile_pending(list(broker_orders))))

    def reconcile_or_raise(self, broker_orders):
        result = self.reconcile(broker_orders)
        if result.alerts:
            raise RuntimeError("order reconciliation produced alerts: " + "; ".join(e.reason for e in result.alerts))
        return result
