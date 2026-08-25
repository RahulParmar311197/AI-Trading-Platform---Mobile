from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from uuid import uuid4

from app.execution_state_store import ExecutionStateStore


class OrderStatus(str, Enum):
    CREATED="CREATED"; RISK_APPROVED="RISK_APPROVED"; SUBMITTED="SUBMITTED"; PARTIALLY_FILLED="PARTIALLY_FILLED"; FILLED="FILLED"; CANCELLED="CANCELLED"; REJECTED="REJECTED"; CLOSED="CLOSED"

@dataclass
class Fill:
    price: float
    quantity: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class Order:
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    stop: float | None = None
    target: float | None = None
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    fills: list[Fill] = field(default_factory=list)

class ExecutionLedger:
    def __init__(self, state_store: ExecutionStateStore | None = None):
        self.orders: dict[str, Order] = {}
        self.client_ids: set[str] = set()
        self.state_store = state_store

    def create(self, symbol: str, side: str, quantity: float, stop: float|None=None, target: float|None=None, client_order_id: str|None=None) -> Order:
        cid = client_order_id or str(uuid4())
        if cid in self.client_ids: raise ValueError("duplicate client_order_id")
        if quantity <= 0: raise ValueError("quantity must be positive")
        order = Order(str(uuid4()), cid, symbol.upper(), side.upper(), quantity, stop, target)
        self.orders[order.order_id] = order
        self.client_ids.add(cid)
        return order

    def transition(self, order_id: str, status: OrderStatus):
        order = self.orders[order_id]
        allowed = {
            OrderStatus.CREATED:{OrderStatus.RISK_APPROVED,OrderStatus.REJECTED},
            OrderStatus.RISK_APPROVED:{OrderStatus.SUBMITTED,OrderStatus.CANCELLED},
            OrderStatus.SUBMITTED:{OrderStatus.PARTIALLY_FILLED,OrderStatus.FILLED,OrderStatus.CANCELLED,OrderStatus.REJECTED},
            OrderStatus.PARTIALLY_FILLED:{OrderStatus.PARTIALLY_FILLED,OrderStatus.FILLED,OrderStatus.CANCELLED},
            OrderStatus.FILLED:{OrderStatus.CLOSED}, OrderStatus.CANCELLED:set(), OrderStatus.REJECTED:set(), OrderStatus.CLOSED:set()
        }
        if status not in allowed[order.status]: raise ValueError(f"invalid transition {order.status}->{status}")
        order.status = status
        if self.state_store is not None:
            if status == OrderStatus.SUBMITTED:
                self.state_store.register_order(order_id=order.order_id, symbol=order.symbol, side=order.side, quantity=order.quantity)
            elif status in {OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                self.state_store.close_order(order_id=order.order_id)
        return order

    def fill(self, order_id: str, price: float, quantity: float):
        order = self.orders[order_id]
        if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}: raise ValueError("order is not fillable")
        if price <= 0 or quantity <= 0 or order.filled_quantity + quantity > order.quantity: raise ValueError("invalid fill")
        previous = order.filled_quantity
        order.filled_quantity += quantity
        order.avg_fill_price = ((order.avg_fill_price * previous) + (price * quantity)) / order.filled_quantity
        order.fills.append(Fill(price, quantity))
        if self.state_store is not None:
            self.state_store.apply_fill(order_id=order.order_id, filled_quantity=quantity)
        order.status = OrderStatus.FILLED if order.filled_quantity == order.quantity else OrderStatus.PARTIALLY_FILLED
        if self.state_store is not None and order.status == OrderStatus.FILLED:
            self.state_store.close_order(order_id=order.order_id)
        return order
