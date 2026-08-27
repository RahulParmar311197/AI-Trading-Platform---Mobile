"""Deterministic in-memory paper broker for safe end-to-end execution tests."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.brokers.base import BrokerAdapter


class PaperBrokerAdapter(BrokerAdapter):
    """Small provider-neutral broker simulator; no network or live orders."""

    def __init__(self, quotes: dict[str, float] | None = None):
        self.quotes = {k: float(v) for k, v in (quotes or {}).items()}
        self._orders: dict[str, dict[str, Any]] = {}
        self._trades: list[dict[str, Any]] = []
        self._positions: dict[str, float] = {}

    def get_quote(self, symbol: str) -> dict[str, Any]:
        price = self.quotes.get(symbol)
        if price is None:
            raise ValueError(f"no paper quote configured for {symbol}")
        return {"symbol": symbol, "last_price": price}

    def get_positions(self) -> list[dict[str, Any]]:
        return [{"symbol": s, "quantity": q} for s, q in self._positions.items() if q]

    def get_orders(self) -> list[dict[str, Any]]:
        return list(self._orders.values())

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        if broker_order_id not in self._orders:
            raise KeyError(broker_order_id)
        return dict(self._orders[broker_order_id])

    def get_trades(self) -> list[dict[str, Any]]:
        return list(self._trades)

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        return [t for t in self._trades if t["order_id"] == broker_order_id]

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        symbol = str(order["symbol"])
        side = str(order["side"]).upper()
        quantity = float(order["quantity"])
        price = float(order.get("price") or self.get_quote(symbol)["last_price"])
        order_id = f"paper-{uuid4().hex}"
        record = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "idempotency_key": order.get("idempotency_key"),
        }
        self._orders[order_id] = record
        signed = quantity if side in {"BUY", "B"} else -quantity
        self._positions[symbol] = self._positions.get(symbol, 0.0) + signed
        self._trades.append({"trade_id": f"trade-{uuid4().hex}", "order_id": order_id, "symbol": symbol, "quantity": quantity, "price": price, "side": side})
        return dict(record)

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        order = self.get_order(broker_order_id)
        if order["status"] == "FILLED":
            return {"order_id": broker_order_id, "status": "REJECTED", "message": "filled paper order cannot be cancelled"}
        order["status"] = "CANCELLED"
        return dict(order)

    def health(self) -> dict[str, Any]:
        return {"broker": "paper", "configured": True, "live_trading_enabled": False}


__all__ = ["PaperBrokerAdapter"]
