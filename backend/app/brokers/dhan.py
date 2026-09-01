from typing import Any

from app.brokers.base import BrokerAdapter
from app.brokers.dhan_client import DhanClient


class DhanAdapter(BrokerAdapter):
    """DhanHQ adapter boundary with safe read-only connectivity.

    Order placement/cancellation are deliberately blocked until the platform's
    execution, risk and reconciliation gates explicitly enable live trading.
    """

    def __init__(self, credentials: dict[str, Any]):
        self.credentials = credentials
        self.access_token = str(credentials.get("access_token", ""))
        self.client = DhanClient(self.access_token) if self.access_token else None

    def _require_client(self) -> DhanClient:
        if self.client is None:
            raise RuntimeError("Dhan broker credentials are not configured; broker snapshot unavailable")
        return self.client

    def get_quote(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Dhan quote integration requires the normalized instrument/security-id mapping"
        )

    def get_positions(self) -> list[dict[str, Any]]:
        result = self._require_client().get_positions()
        if not isinstance(result, list):
            raise RuntimeError("Dhan positions response is not an authoritative list")
        return result

    def get_orders(self) -> list[dict[str, Any]]:
        result = self._require_client().get_orders()
        if not isinstance(result, list):
            raise RuntimeError("Dhan orders response is not an authoritative list")
        return result

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        result = self._require_client().get_order(broker_order_id)
        if not isinstance(result, dict):
            raise RuntimeError("Dhan order response is not an authoritative object")
        return result

    def get_trades(self) -> list[dict[str, Any]]:
        result = self._require_client().get_trades()
        if not isinstance(result, list):
            raise RuntimeError("Dhan trades response is not an authoritative list")
        return result

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        result = self._require_client().get_trades_for_order(broker_order_id)
        if not isinstance(result, list):
            raise RuntimeError("Dhan order-trades response is not an authoritative list")
        return result

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "Live Dhan order placement is disabled until execution validation is complete"
        )

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Live Dhan order cancellation is disabled until execution validation is complete"
        )

    def health(self) -> dict[str, Any]:
        if not self.client:
            return {
                "broker": "dhan",
                "configured": False,
                "authenticated": False,
                "live_trading_enabled": False,
            }
        try:
            status = self.client.health()
            return {**status, "configured": True, "live_trading_enabled": False}
        except Exception as exc:
            return {
                "broker": "dhan",
                "configured": True,
                "authenticated": False,
                "live_trading_enabled": False,
                "error": type(exc).__name__,
            }
