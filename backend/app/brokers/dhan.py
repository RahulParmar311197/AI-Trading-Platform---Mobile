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
        self.dhan_client_id = str(credentials.get("dhan_client_id", "")).strip() or None
        self.client = DhanClient(self.access_token) if self.access_token else None

    def _require_client(self) -> DhanClient:
        if self.client is None:
            raise RuntimeError("Dhan broker credentials are not configured; broker snapshot unavailable")
        return self.client

    def _validate_trade_records(self, records: list[dict[str, Any]], *, expected_order_id: str | None = None) -> list[dict[str, Any]]:
        seen_trade_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                raise RuntimeError("Dhan trade response contains a non-object record")
            order_id = str(record.get("orderId") or "").strip()
            if not order_id:
                raise RuntimeError("Dhan trade response missing broker order identity")
            if expected_order_id is not None and order_id != str(expected_order_id).strip():
                raise RuntimeError("Dhan trade response order identity does not match requested order")
            trade_id = str(record.get("exchangeTradeId") or "").strip()
            if not trade_id:
                raise RuntimeError("Dhan trade response missing trade identity")
            if trade_id in seen_trade_ids:
                raise RuntimeError("Dhan trade response contains duplicate trade identity")
            seen_trade_ids.add(trade_id)
            if self.dhan_client_id is not None:
                response_client_id = str(record.get("dhanClientId") or "").strip()
                if not response_client_id or response_client_id != self.dhan_client_id:
                    raise RuntimeError("Dhan trade response account identity does not match configured account")
            try:
                quantity = float(record.get("tradedQuantity"))
                price = float(record.get("tradedPrice"))
            except (TypeError, ValueError):
                raise RuntimeError("Dhan trade response has invalid quantity or price") from None
            if quantity <= 0:
                raise RuntimeError("Dhan trade response requires positive traded quantity")
            if price <= 0:
                raise RuntimeError("Dhan trade response requires positive traded price")
            normalized.append(dict(record))
        return normalized

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
        return self._validate_trade_records(result)

    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        result = self._require_client().get_trades_for_order(broker_order_id)
        if not isinstance(result, list):
            raise RuntimeError("Dhan order-trades response is not an authoritative list")
        return self._validate_trade_records(result, expected_order_id=broker_order_id)

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
