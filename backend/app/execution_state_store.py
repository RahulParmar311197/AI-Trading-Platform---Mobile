from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.internal_trading_state_provider import InternalTradingState, InternalTradingStateProvider


@dataclass(frozen=True)
class ExecutionOrderState:
    order_id: str
    symbol: str
    side: str
    quantity: float
    filled_quantity: float = 0.0


class ExecutionStateStore(InternalTradingStateProvider):
    """Thread-safe internal state updated by order/fill lifecycle events."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._positions: dict[str, float] = {}
        self._orders: dict[str, ExecutionOrderState] = {}

    def register_order(self, *, order_id: str, symbol: str, side: str, quantity: float) -> None:
        if not order_id or not symbol or quantity <= 0:
            raise ValueError("order_id, symbol and positive quantity are required")
        with self._lock:
            self._orders[order_id] = ExecutionOrderState(order_id, symbol.upper(), side.upper(), float(quantity), 0.0)

    def apply_fill(self, *, order_id: str, filled_quantity: float) -> None:
        if filled_quantity <= 0:
            raise ValueError("filled_quantity must be positive")
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise KeyError(f"unknown order: {order_id}")
            new_filled = order.filled_quantity + float(filled_quantity)
            if new_filled > order.quantity:
                raise ValueError("fill exceeds order quantity")
            self._orders[order_id] = ExecutionOrderState(order.order_id, order.symbol, order.side, order.quantity, new_filled)
            signed = new_filled - order.filled_quantity
            multiplier = -1.0 if order.side == "SELL" else 1.0
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + multiplier * signed

    def close_order(self, *, order_id: str) -> None:
        with self._lock:
            self._orders.pop(order_id, None)

    def get_state(self) -> InternalTradingState:
        with self._lock:
            return InternalTradingState(dict(self._positions), frozenset(self._orders.keys()))
