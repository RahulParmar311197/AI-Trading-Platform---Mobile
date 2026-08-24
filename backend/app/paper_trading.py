from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count

from app.trade_plan import TradeAction, TradePlan


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    symbol: str
    action: TradeAction
    quantity: int
    entry: float
    stop_loss: float
    take_profit: float
    status: str
    created_at: datetime
    filled_quantity: int = 0


class PaperBroker:
    """In-memory broker for safe end-to-end execution testing with reconciliation."""

    def __init__(self, starting_cash: float = 100000.0):
        if starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        self.cash = float(starting_cash)
        self.orders: dict[str, PaperOrder] = {}
        self._ids = count(1)

    def submit(self, plan: TradePlan) -> str:
        if plan.expires_at <= datetime.now(timezone.utc):
            raise ValueError("trade plan expired")
        order_id = f"PAPER-{next(self._ids):06d}"
        order = PaperOrder(order_id, plan.symbol.upper(), plan.action, plan.quantity, plan.entry, plan.stop_loss, plan.take_profit, "PENDING", datetime.now(timezone.utc), 0)
        self.orders[order_id] = order
        return order_id

    def fill(self, order_id: str, quantity: int | None = None, price: float | None = None) -> PaperOrder:
        order = self.orders.get(order_id)
        if order is None or order.status not in {"PENDING", "PARTIAL"}:
            raise ValueError("order is not fillable")
        fill_qty = quantity if quantity is not None else order.quantity - order.filled_quantity
        if fill_qty <= 0 or order.filled_quantity + fill_qty > order.quantity:
            raise ValueError("invalid fill quantity")
        fill_price = price if price is not None else order.entry
        if fill_price <= 0:
            raise ValueError("fill price must be positive")
        filled = order.filled_quantity + fill_qty
        status = "FILLED" if filled == order.quantity else "PARTIAL"
        updated = PaperOrder(order.order_id, order.symbol, order.action, order.quantity, fill_price, order.stop_loss, order.take_profit, status, order.created_at, filled)
        self.orders[order_id] = updated
        return updated

    def cancel(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if order is None or order.status not in {"PENDING", "PARTIAL"}:
            return False
        self.orders[order_id] = PaperOrder(order.order_id, order.symbol, order.action, order.quantity, order.entry, order.stop_loss, order.take_profit, "CANCELLED", order.created_at, order.filled_quantity)
        return True

    def reconcile(self) -> list[str]:
        errors: list[str] = []
        for order in self.orders.values():
            if order.filled_quantity < 0 or order.filled_quantity > order.quantity:
                errors.append(f"invalid fill quantity: {order.order_id}")
            if order.status == "FILLED" and order.filled_quantity != order.quantity:
                errors.append(f"filled order quantity mismatch: {order.order_id}")
            if order.status == "PENDING" and order.filled_quantity != 0:
                errors.append(f"pending order has fills: {order.order_id}")
        return errors

    def snapshot(self) -> dict:
        return {"cash": self.cash, "orders": [o.__dict__ for o in self.orders.values()]}
