from __future__ import annotations

import hashlib
import json
from typing import Any

from app.broker_events import BrokerEventType, BrokerOrderEvent


_STATUS_MAP = {
    "TRANSIT": BrokerEventType.SUBMITTED,
    "PENDING": BrokerEventType.ACKNOWLEDGED,
    "PART_TRADED": BrokerEventType.PARTIALLY_FILLED,
    "TRADED": BrokerEventType.FILLED,
    "REJECTED": BrokerEventType.REJECTED,
    "CANCELLED": BrokerEventType.CANCELLED,
    "EXPIRED": BrokerEventType.UNKNOWN,
}


def normalize_dhan_order(payload: dict[str, Any]) -> BrokerOrderEvent:
    """Normalize a Dhan v2 order/postback payload into the core event contract."""
    broker_order_id = str(payload.get("orderId", "")).strip()
    if not broker_order_id:
        raise ValueError("Dhan orderId is required")

    status = str(payload.get("orderStatus", "")).strip().upper()
    event_type = _STATUS_MAP.get(status, BrokerEventType.UNKNOWN)

    filled = payload.get("filled_qty", payload.get("filledQty", 0)) or 0
    fill_price = payload.get("averageTradedPrice", 0) or 0
    try:
        filled_quantity = float(filled)
        price = float(fill_price)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid Dhan fill values") from exc

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id:
        stable = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        event_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()

    return BrokerOrderEvent(
        broker="dhan",
        broker_order_id=broker_order_id,
        event_id=event_id,
        event_type=event_type,
        filled_quantity=filled_quantity,
        fill_price=price if event_type in {
            BrokerEventType.PARTIALLY_FILLED,
            BrokerEventType.FILLED,
        } else None,
    )
