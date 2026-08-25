from __future__ import annotations

from datetime import datetime
from typing import Any

from app.canonical_execution_event import CanonicalExecutionEvent, CanonicalExecutionEventType


class ExecutionEventNormalizer:
    """Normalize broker-specific callback dictionaries into canonical events."""

    _TYPE_MAP = {
        "SUBMITTED": CanonicalExecutionEventType.SUBMITTED,
        "OPEN": CanonicalExecutionEventType.ACKNOWLEDGED,
        "ACK": CanonicalExecutionEventType.ACKNOWLEDGED,
        "ACKNOWLEDGED": CanonicalExecutionEventType.ACKNOWLEDGED,
        "PARTIAL_FILL": CanonicalExecutionEventType.PARTIAL_FILL,
        "PARTIAL": CanonicalExecutionEventType.PARTIAL_FILL,
        "FILL": CanonicalExecutionEventType.FILLED,
        "FILLED": CanonicalExecutionEventType.FILLED,
        "COMPLETE": CanonicalExecutionEventType.FILLED,
        "CANCELLED": CanonicalExecutionEventType.CANCELLED,
        "CANCELED": CanonicalExecutionEventType.CANCELLED,
        "REJECTED": CanonicalExecutionEventType.REJECTED,
    }

    @classmethod
    def normalize(cls, payload: dict[str, Any], *, broker: str) -> CanonicalExecutionEvent:
        kind = str(payload.get("event_type") or payload.get("status") or payload.get("type") or "").upper()
        try:
            event_type = cls._TYPE_MAP[kind]
        except KeyError as exc:
            raise ValueError(f"unsupported broker execution event type: {kind}") from exc
        event_id = str(payload.get("event_id") or payload.get("trade_id") or payload.get("execution_id") or "")
        broker_order_id = str(payload.get("broker_order_id") or payload.get("order_id") or "")
        client_order_id = str(payload.get("client_order_id") or payload.get("client_id") or broker_order_id)
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        account_id = payload.get("broker_account_id")
        return CanonicalExecutionEvent(
            event_id=event_id,
            broker_order_id=broker_order_id,
            client_order_id=client_order_id,
            symbol=str(payload.get("symbol") or payload.get("tradingsymbol") or ""),
            side=str(payload.get("side") or payload.get("transaction_type") or ""),
            event_type=event_type,
            quantity=float(payload.get("quantity") or payload.get("filled_quantity") or payload.get("fill_qty") or 0),
            price=float(payload["price"]) if payload.get("price") is not None else None,
            timestamp=timestamp,
            broker=broker,
            broker_account_id=int(account_id) if account_id is not None else None,
            broker_route=str(payload["broker_route"]) if payload.get("broker_route") else None,
        )
