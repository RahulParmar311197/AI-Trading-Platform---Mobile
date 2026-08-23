from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SUBMISSION_INTENT = "SUBMISSION_INTENT"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class OrderRecord:
    order_id: str
    symbol: str
    side: str
    quantity: float
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    applied_fill_quantity: float = 0.0
    applied_fill_value: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PositionRecord:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    status: PositionStatus = PositionStatus.OPEN
    exit_price: float | None = None
    realized_pnl: float = 0.0


class OrderLifecycle:
    def __init__(self):
        self.orders = {}
        self.positions = {}

    def create(self, order_id, symbol, side, quantity):
        if order_id in self.orders:
            raise ValueError("duplicate order_id")
        self.orders[order_id] = OrderRecord(order_id, symbol.upper(), side.upper(), quantity)
        return self.orders[order_id]

    def transition(self, order_id, status, filled_quantity=0.0, fill_price=None):
        order = self.orders[order_id]
        if status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED) and not 0 <= filled_quantity <= order.quantity:
            raise ValueError("invalid filled quantity")
        if filled_quantity < order.applied_fill_quantity:
            raise ValueError("filled quantity cannot move backwards")
        order.status = status
        order.filled_quantity = filled_quantity
        if fill_price is not None:
            fill_price = float(fill_price)
            if fill_price <= 0:
                raise ValueError("fill price must be positive")
            order.average_fill_price = fill_price
        order.updated_at = datetime.now(timezone.utc)

        delta_quantity = filled_quantity - order.applied_fill_quantity
        if delta_quantity > 0:
            if order.average_fill_price is None:
                raise ValueError("fill price is required when applying a fill")
            cumulative_value = filled_quantity * order.average_fill_price
            delta_value = cumulative_value - order.applied_fill_value
            if delta_value <= 0:
                raise ValueError("cumulative fill value cannot move backwards")
            delta_price = delta_value / delta_quantity
            self._apply_position_delta(order, delta_quantity, delta_price)
            order.applied_fill_quantity = filled_quantity
            order.applied_fill_value = cumulative_value
        return order

    def _apply_position_delta(self, order, quantity, price):
        existing = self.positions.get(order.symbol)
        if existing is None:
            self.positions[order.symbol] = PositionRecord(order.symbol, order.side, quantity, price)
            return
        if existing.side == order.side:
            total = existing.quantity + quantity
            existing.entry_price = ((existing.entry_price * existing.quantity) + (price * quantity)) / total
            existing.quantity = total
            return

        qty = min(existing.quantity, quantity)
        pnl = (price - existing.entry_price) * qty * (1 if existing.side == "BUY" else -1)
        existing.realized_pnl += pnl
        existing.quantity -= qty
        if existing.quantity <= 0:
            existing.status = PositionStatus.CLOSED
            existing.exit_price = price
            del self.positions[order.symbol]
