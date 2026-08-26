from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx

from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_order_snapshot import BrokerOrderSnapshot


@dataclass(frozen=True)
class UpstoxConfig:
    access_token: str
    base_url: str = "https://api-hft.upstox.com"
    live_enabled: bool = False
    timeout_seconds: float = 10.0
    slice_orders: bool = False
    market_protection: int = -1

    @classmethod
    def from_env(cls) -> "UpstoxConfig":
        return cls(
            access_token=os.getenv("UPSTOX_ACCESS_TOKEN", ""),
            base_url=os.getenv("UPSTOX_API_BASE_URL", "https://api-hft.upstox.com").rstrip("/"),
            live_enabled=os.getenv("UPSTOX_LIVE_ENABLED", "false").lower() == "true",
            timeout_seconds=float(os.getenv("UPSTOX_HTTP_TIMEOUT_SECONDS", "10")),
            slice_orders=os.getenv("UPSTOX_SLICE", "false").lower() == "true",
            market_protection=int(os.getenv("UPSTOX_MARKET_PROTECTION", "-1")),
        )


class UpstoxHttpTransport:
    def __init__(self, timeout_seconds: float = 10.0, client: httpx.Client | None = None):
        if timeout_seconds <= 0:
            raise ValueError("Upstox HTTP timeout must be greater than zero")
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", self.timeout_seconds)
        return self.client.request(method, url, **kwargs)

    def close(self) -> None:
        self.client.close()


class UpstoxAdapter(BrokerAdapter):
    name = "upstox"

    def __init__(self, config: UpstoxConfig | None = None, transport: Any | None = None):
        self.config = config or UpstoxConfig.from_env()
        self.transport = transport or UpstoxHttpTransport(self.config.timeout_seconds)

    def _require_live(self) -> None:
        if not self.config.live_enabled:
            raise RuntimeError("UPSTOX_LIVE_ENABLED is false")
        if not self.config.access_token:
            raise RuntimeError("Upstox access token is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.access_token}",
        }

    @staticmethod
    def _validate_tag(client_order_id: str) -> str:
        if not client_order_id or len(client_order_id) > 40:
            raise ValueError("Upstox tag must be between 1 and 40 characters")
        return client_order_id

    @staticmethod
    def _status(data: dict[str, Any]) -> str:
        return str(data.get("status") or data.get("order_status") or "UNKNOWN").upper()

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderUpdate:
        self._require_live()
        tag = self._validate_tag(request.client_order_id)
        order_type = request.order_type.upper()
        if order_type in {"MARKET", "SL-M"} and not (-1 <= self.config.market_protection <= 25):
            raise ValueError("Upstox market protection must be -1 or between 1 and 25")
        payload = {
            "quantity": int(request.quantity),
            "product": {"INTRADAY": "I", "I": "I", "CNC": "D", "D": "D", "MTF": "MTF"}.get(request.product_type.upper(), request.product_type.upper()),
            "validity": request.validity.upper(),
            "price": float(request.price or 0),
            "tag": tag,
            "instrument_token": request.security_id,
            "order_type": order_type,
            "transaction_type": request.side.upper(),
            "disclosed_quantity": 0,
            "trigger_price": float(request.trigger_price or request.stop or 0),
            "is_amo": False,
            "slice": self.config.slice_orders,
        }
        if order_type in {"MARKET", "SL-M"}:
            payload["market_protection"] = self.config.market_protection
        response = self.transport.request("POST", f"{self.config.base_url}/v3/order/place", headers=self._headers(), json=payload)
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        order_ids = data.get("order_ids") or ([data.get("order_id")] if data.get("order_id") else [])
        if not order_ids:
            raise RuntimeError("Upstox placement response did not contain an order id")
        return BrokerOrderUpdate(order_id=str(order_ids[0]), status="SUBMITTED", client_order_id=tag, symbol=request.symbol, side=request.side.upper(), quantity=request.quantity, price=request.price, message=";".join(map(str, order_ids)))

    def find_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        self._require_live()
        tag = self._validate_tag(client_order_id)
        response = self.transport.request("GET", f"{self.config.base_url}/v2/order/history", headers=self._headers(), params={"tag": tag})
        if getattr(response, "status_code", None) == 404:
            return None
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        if isinstance(data, dict):
            data = data.get("orders", [data])
        if not isinstance(data, list):
            return None
        matches = [dict(order) for order in data if str(order.get("tag", tag)) == tag]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        return {"client_order_id": tag, "orders": matches, "multi_order": True}

    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        self._require_live()
        response = self.transport.request("GET", f"{self.config.base_url}/v2/order/details", headers=self._headers(), params={"order_id": broker_order_id})
        response.raise_for_status()
        return response.json().get("data", response.json())

    def get_orders(self) -> list[dict[str, Any]]:
        self._require_live()
        response = self.transport.request("GET", f"{self.config.base_url}/v2/order/retrieve-all", headers=self._headers())
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        if not isinstance(data, list):
            raise RuntimeError("Upstox retrieve-all order response is not a complete order list")
        return data

    def get_order_snapshot(self) -> BrokerOrderSnapshot:
        """Return the retrieve-all result only when the API returned the expected complete list."""
        self._require_live()
        response = self.transport.request(
            "GET",
            f"{self.config.base_url}/v2/order/retrieve-all",
            headers=self._headers(),
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        if not isinstance(data, list):
            raise RuntimeError("Upstox retrieve-all order snapshot is not authoritative")
        return BrokerOrderSnapshot(
            orders=[dict(order) for order in data],
            complete=True,
            source="upstox",
        )

    def get_trades_by_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        self._require_live()
        response = self.transport.request("GET", f"{self.config.base_url}/v2/order/trades", headers=self._headers(), params={"order_id": broker_order_id})
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        return data if isinstance(data, list) else []

    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        self._require_live()
        response = self.transport.request("DELETE", f"{self.config.base_url}/v3/order/cancel", headers=self._headers(), params={"order_id": broker_order_id})
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        return BrokerOrderUpdate(order_id=str(data.get("order_id", broker_order_id)), status="CANCELLED", message=str(data.get("message", "")) or None)

    def get_positions(self) -> list[dict[str, Any]]:
        self._require_live()
        response = self.transport.request("GET", f"{self.config.base_url}/v2/portfolio/short-term-positions", headers=self._headers())
        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)
        return data if isinstance(data, list) else []

    def get_account(self) -> dict[str, Any]:
        self._require_live()
        response = self.transport.request("GET", f"{self.config.base_url}/v2/user/get-funds-and-margin", headers=self._headers())
        response.raise_for_status()
        return response.json().get("data", response.json())
