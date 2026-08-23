from __future__ import annotations

from dataclasses import dataclass
import os
import uuid

from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate


@dataclass(frozen=True)
class DhanConfig:
    client_id: str
    access_token: str
    base_url: str = "https://api.dhan.co/v2"
    live_enabled: bool = False

    @classmethod
    def from_env(cls) -> "DhanConfig":
        return cls(
            client_id=os.getenv("DHAN_CLIENT_ID", ""),
            access_token=os.getenv("DHAN_ACCESS_TOKEN", ""),
            base_url=os.getenv("DHAN_API_BASE_URL", "https://api.dhan.co/v2").rstrip("/"),
            live_enabled=os.getenv("DHAN_LIVE_ENABLED", "false").lower() == "true",
        )


class DhanAdapter(BrokerAdapter):
    """DhanHQ v2 adapter boundary.

    Live submission is deliberately disabled unless explicitly enabled and
    the adapter is constructed with credentials. HTTP transport is injected
    so unit tests never contact the broker.
    """

    name = "dhan"

    def __init__(self, config: DhanConfig | None = None, transport=None):
        self.config = config or DhanConfig.from_env()
        self.transport = transport

    def _require_live(self) -> None:
        if not self.config.live_enabled:
            raise RuntimeError("DHAN_LIVE_ENABLED is false")
        if not self.config.client_id or not self.config.access_token:
            raise RuntimeError("Dhan credentials are not configured")
        if self.transport is None:
            raise RuntimeError("Dhan HTTP transport is not configured")

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderUpdate:
        self._require_live()
        payload = {
            "dhanClientId": self.config.client_id,
            "correlationId": request.client_order_id or uuid.uuid4().hex[:20],
            "transactionType": request.side.upper(),
            "exchangeSegment": request.exchange_segment,
            "productType": request.product_type,
            "orderType": request.order_type,
            "validity": request.validity,
            "securityId": request.security_id,
            "quantity": request.quantity,
            "price": request.price,
            "triggerPrice": request.trigger_price,
        }
        response = self.transport.post(
            f"{self.config.base_url}/orders",
            headers={"Content-Type": "application/json", "access-token": self.config.access_token},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return BrokerOrderUpdate(order_id=str(data["orderId"]), status=str(data["orderStatus"]))

    def cancel_order(self, order_id: str) -> BrokerOrderUpdate:
        self._require_live()
        response = self.transport.delete(
            f"{self.config.base_url}/orders/{order_id}",
            headers={"Content-Type": "application/json", "access-token": self.config.access_token},
        )
        response.raise_for_status()
        data = response.json()
        return BrokerOrderUpdate(order_id=str(data["orderId"]), status=str(data["orderStatus"]))
