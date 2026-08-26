from typing import Any

from app.brokers.base import BrokerAdapter


class UpstoxAdapter(BrokerAdapter):
    """Upstox adapter boundary; live HTTP integration is intentionally disabled."""

    def __init__(self, credentials: dict[str, Any]):
        self.credentials = credentials

    def get_quote(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError("Upstox quote integration is pending configuration")

    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Upstox positions integration is pending configuration")

    def get_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Upstox order reconciliation integration is pending configuration")

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        raise NotImplementedError("Upstox order lookup integration is pending configuration")

    def get_trades(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Upstox trade reconciliation integration is pending configuration")

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Upstox order-trade lookup integration is pending configuration")

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Live Upstox order placement is disabled until broker validation is complete")

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        raise NotImplementedError("Upstox order cancellation integration is pending configuration")

    def health(self) -> dict[str, Any]:
        return {
            "broker": "upstox",
            "configured": bool(self.credentials),
            "live_trading_enabled": False,
        }
