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

    def get_quote(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError(
            "Dhan quote integration requires the normalized instrument/security-id mapping"
        )

    def get_positions(self) -> list[dict[str, Any]]:
        if not self.client:
            return []
        result = self.client.get_positions()
        return result if isinstance(result, list) else []

    def get_orders(self) -> list[dict[str, Any]]:
        if not self.client:
            return []
        result = self.client.get_orders()
        return result if isinstance(result, list) else []

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        if not self.client:
            return {}
        result = self.client.get_order(broker_order_id)
        return result if isinstance(result, dict) else {}

    def get_trades(self) -> list[dict[str, Any]]:
        if not self.client:
            return []
        result = self.client.get_trades()
        return result if isinstance(result, list) else []

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        if not self.client:
            return []
        result = self.client.get_trades_for_order(broker_order_id)
        return result if isinstance(result, list) else []

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
