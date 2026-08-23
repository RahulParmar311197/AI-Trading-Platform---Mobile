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


class PaperBroker:
    """In-memory broker for safe end-to-end execution testing."""

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
        order = PaperOrder(order_id, plan.symbol.upper(), plan.action, plan.quantity, plan.entry, plan.stop_loss, plan.take_profit, "FILLED", datetime.now(timezone.utc))
        self.orders[order_id] = order
        return order_id

    def cancel(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if order is None or order.status != "FILLED":
            return False
        self.orders[order_id] = PaperOrder(order.order_id, order.symbol, order.action, order.quantity, order.entry, order.stop_loss, order.take_profit, "CANCELLED", order.created_at)
        return True

    def snapshot(self) -> dict:
        return {"cash": self.cash, "orders": [o.__dict__ for o in self.orders.values()]}
