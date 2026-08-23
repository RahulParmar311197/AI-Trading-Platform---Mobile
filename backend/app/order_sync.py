from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CanonicalOrderStatus(str, Enum):
    TRANSIT = "TRANSIT"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


_STATUS_MAP = {
    "TRANSIT": CanonicalOrderStatus.TRANSIT,
    "PENDING": CanonicalOrderStatus.PENDING,
    "TRADED": CanonicalOrderStatus.FILLED,
    "REJECTED": CanonicalOrderStatus.REJECTED,
    "CANCELLED": CanonicalOrderStatus.CANCELLED,
    "EXPIRED": CanonicalOrderStatus.EXPIRED,
}


@dataclass(frozen=True)
class OrderUpdate:
    order_id: str
    status: CanonicalOrderStatus
    quantity: int
    filled_quantity: int
    average_price: float | None = None
    correlation_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def normalize_status(status: str, filled_quantity: int = 0, quantity: int = 0) -> CanonicalOrderStatus:
    normalized = status.upper().strip()
    if normalized == "TRADED":
        return CanonicalOrderStatus.FILLED
    if quantity > 0 and 0 < filled_quantity < quantity:
        return CanonicalOrderStatus.PARTIALLY_FILLED
    return _STATUS_MAP.get(normalized, CanonicalOrderStatus.UNKNOWN)


def from_dhan_postback(payload: dict) -> OrderUpdate:
    order_id = str(payload.get("orderId", "")).strip()
    if not order_id:
        raise ValueError("orderId is required")
    quantity = int(payload.get("quantity", 0) or 0)
    filled = int(payload.get("filled_qty", 0) or 0)
    if quantity < 0 or filled < 0 or filled > quantity:
        raise ValueError("invalid quantity/fill values")
    status = normalize_status(str(payload.get("orderStatus", "UNKNOWN")), filled, quantity)
    average = payload.get("averageTradedPrice", payload.get("price"))
    return OrderUpdate(
        order_id=order_id,
        status=status,
        quantity=quantity,
        filled_quantity=filled,
        average_price=float(average) if average is not None else None,
        correlation_id=payload.get("correlationId"),
        error_code=payload.get("omsErrorCode"),
        error_message=payload.get("omsErrorDescription"),
    )
