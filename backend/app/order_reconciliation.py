from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.order_lifecycle import OrderLifecycle, OrderStatus


class ReconciliationAction(str, Enum):
    NOOP = "NOOP"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ALERT = "ALERT"


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


@dataclass(frozen=True)
class ReconciliationEvent:
    order_id: str
    action: ReconciliationAction
    reason: str


class OrderReconciler:
    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle

    def _find_local(self, remote: BrokerOrder):
        direct = self.lifecycle.orders.get(remote.order_id)
        if direct is not None:
            return direct
        for order in self.lifecycle.orders.values():
            if order.broker_order_id == remote.order_id:
                return order
            if remote.client_order_id and order.order_id == remote.client_order_id:
                return order
        return None

    @staticmethod
    def _validate_identity(local, remote: BrokerOrder):
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
            local = self._find_local(remote)
            if local is None:
                local_id = remote.client_order_id or remote.order_id
                if local_id in self.lifecycle.orders:
                    events.append(ReconciliationEvent(remote.order_id, ReconciliationAction.ALERT, "BROKER_CLIENT_ORDER_ID_COLLISION"))
                    continue
                try:
                    self.lifecycle.create(local_id, remote.symbol, remote.side, remote.quantity)
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
