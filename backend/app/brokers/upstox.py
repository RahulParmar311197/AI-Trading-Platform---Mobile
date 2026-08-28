from __future__ import annotations

from typing import Any

from app.brokers.base import BrokerAdapter
from app.brokers.upstox_client import UpstoxClient
from app.config import get_settings


class UpstoxAdapter(BrokerAdapter):
    """Account-scoped Upstox adapter backed by the authenticated REST client."""

    def __init__(self, credentials: dict[str, Any]):
        access_token = credentials.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Upstox credentials require access_token")
        self.client = UpstoxClient(access_token)
        self._live_trading_enabled = get_settings().live_trading_enabled

    def get_quote(self, symbol: str) -> dict[str, Any]:
        return self.client.get_quote(symbol)

    def get_positions(self) -> list[dict[str, Any]]:
        return self.client.get_positions()

    def get_orders(self) -> list[dict[str, Any]]:
        return self.client.get_orders()

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        return self.client.get_order(broker_order_id)

    def get_trades(self) -> list[dict[str, Any]]:
        return self.client.get_trades()

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        return self.client.get_trades_for_order(broker_order_id)

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if not self._live_trading_enabled:
            raise RuntimeError("Live Upstox order placement is disabled by LIVE_TRADING_ENABLED")
        return self.client.place_order(order)

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        if not self._live_trading_enabled:
            raise RuntimeError("Live Upstox order cancellation is disabled by LIVE_TRADING_ENABLED")
        return self.client.cancel_order(broker_order_id)

    def health(self) -> dict[str, Any]:
        result = self.client.health()
        result["live_trading_enabled"] = self._live_trading_enabled
        return result
