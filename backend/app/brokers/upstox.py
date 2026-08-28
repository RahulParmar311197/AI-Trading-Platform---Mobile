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
        broker_user_id = credentials.get("broker_user_id")
        if not isinstance(broker_user_id, str) or not broker_user_id.strip():
            raise ValueError("Upstox credentials require broker_user_id")
        self.client = UpstoxClient(access_token)
        self.broker_user_id = broker_user_id.strip()
        self._live_trading_enabled = get_settings().live_trading_enabled

    def verify_authenticated_identity(self) -> dict[str, Any]:
        """Prove that the bearer token still belongs to the provisioned Upstox user."""
        profile = self.client.get_profile()
        returned_broker = profile.get("broker")
        returned_user_id = profile.get("user_id")
        if returned_broker not in (None, "UPSTOX"):
            raise RuntimeError("Upstox authenticated broker identity mismatch")
        if not isinstance(returned_user_id, str) or returned_user_id.strip() != self.broker_user_id:
            raise RuntimeError("Upstox authenticated user identity mismatch")
        return profile

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
