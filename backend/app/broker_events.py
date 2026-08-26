from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.order_lifecycle import OrderLifecycle, OrderStatus


class BrokerEventType(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BrokerOrderEvent:
    broker: str
    broker_order_id: str
    event_id: str
    event_type: BrokerEventType
    filled_quantity: float = 0.0
    fill_price: float | None = None


def ingest_event(lifecycle: OrderLifecycle, local_order_id: str, event: BrokerOrderEvent):
    """Apply a normalized broker event to the existing lifecycle.

    Broker-specific payload parsing belongs in adapters. Unknown states fail closed
    by moving the existing order into reconciliation rather than guessing.
    """
    if not event.event_id.strip() or not event.broker_order_id.strip():
        raise ValueError("broker event identifiers are required")

    order = lifecycle.orders[local_order_id]
    status_map = {
        BrokerEventType.SUBMITTED: OrderStatus.SUBMITTED,
        BrokerEventType.ACKNOWLEDGED: OrderStatus.SUBMITTED,
        BrokerEventType.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
        BrokerEventType.FILLED: OrderStatus.FILLED,
        BrokerEventType.REJECTED: OrderStatus.REJECTED,
        BrokerEventType.CANCELLED: OrderStatus.CANCELLED,
        BrokerEventType.UNKNOWN: OrderStatus.PENDING_RECONCILIATION,
    }
    target = status_map[event.event_type]
    order.broker_order_id = event.broker_order_id

    if event.event_type in {BrokerEventType.PARTIALLY_FILLED, BrokerEventType.FILLED}:
        if event.filled_quantity <= 0 or event.fill_price is None or event.fill_price <= 0:
            raise ValueError("fill events require positive quantity and price")
        return lifecycle.transition(
            local_order_id,
            target,
            filled_quantity=event.filled_quantity,
            fill_price=event.fill_price,
        )

    return lifecycle.transition(local_order_id, target)
