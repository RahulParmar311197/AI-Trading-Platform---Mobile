from __future__ import annotations

from dataclasses import dataclass
import os
import uuid

import httpx

from app.broker_adapter import BrokerAdapter, BrokerHealth, BrokerOrderRequest, BrokerOrderUpdate, normalize_broker_update
from app.broker_snapshot import BrokerSnapshot, dhan_snapshot
from app.broker_position_snapshot import BrokerPositionSnapshot

@dataclass(frozen=True)
class DhanConfig:
    client_id: str
    access_token: str
    base_url: str = "https://api.dhan.co/v2"
    live_enabled: bool = False
    timeout_seconds: float = 10.0
    @classmethod
    def from_env(cls) -> "DhanConfig":
        return cls(client_id=os.getenv("DHAN_CLIENT_ID", ""), access_token=os.getenv("DHAN_ACCESS_TOKEN", ""), base_url=os.getenv("DHAN_API_BASE_URL", "https://api.dhan.co/v2").rstrip("/"), live_enabled=os.getenv("DHAN_LIVE_ENABLED", "false").lower() == "true", timeout_seconds=float(os.getenv("DHAN_HTTP_TIMEOUT_SECONDS", "10")))

class DhanHttpTransport:
    def __init__(self, timeout_seconds: float = 10.0, client: httpx.Client | None = None):
        if timeout_seconds <= 0: raise ValueError("Dhan HTTP timeout must be greater than zero")
        self.timeout_seconds = timeout_seconds; self.client = client or httpx.Client(timeout=timeout_seconds)
    def post(self, url, **kwargs): kwargs.setdefault("timeout", self.timeout_seconds); return self.client.post(url, **kwargs)
    def get(self, url, **kwargs): kwargs.setdefault("timeout", self.timeout_seconds); return self.client.get(url, **kwargs)
    def delete(self, url, **kwargs): kwargs.setdefault("timeout", self.timeout_seconds); return self.client.delete(url, **kwargs)
    def close(self): self.client.close()

class DhanAdapter(BrokerAdapter):
    name = "dhan"
    def __init__(self, config: DhanConfig | None = None, transport=None): self.config = config or DhanConfig.from_env(); self.transport = transport or DhanHttpTransport(self.config.timeout_seconds)
    def _require_live(self) -> None:
        if not self.config.live_enabled: raise RuntimeError("DHAN_LIVE_ENABLED is false")
        if not self.config.client_id or not self.config.access_token: raise RuntimeError("Dhan credentials are not configured")
        if self.transport is None: raise RuntimeError("Dhan HTTP transport is not configured")
    def _headers(self) -> dict[str, str]: return {"Content-Type": "application/json", "access-token": self.config.access_token}
    @staticmethod
    def _require_order_id(broker_order_id: str) -> str:
        order_id = str(broker_order_id or "").strip()
        if not order_id: raise ValueError("Dhan broker order ID is required")
        return order_id
    def health(self) -> BrokerHealth:
        if not self.config.live_enabled: return BrokerHealth("dhan", False, False, False, "Dhan live trading is disabled")
        if not self.config.client_id or not self.config.access_token: return BrokerHealth("dhan", False, False, True, "Dhan credentials are not configured")
        try: self.get_account(); return BrokerHealth("dhan", True, True, True, "authenticated")
        except Exception as exc: return BrokerHealth("dhan", False, False, True, f"health check failed: {exc}")
    @staticmethod
    def _placement_status(raw_status: str) -> str:
        status = str(raw_status or "").strip().upper()
        return {"TRANSIT": "NEW", "PENDING": "NEW", "PART_TRADED": "PARTIALLY_FILLED", "REJECTED": "REJECTED", "CANCELLED": "CANCELLED", "TRADED": "FILLED", "EXPIRED": "CANCELLED"}.get(status, status)
    @staticmethod
    def _fill_fields(data: dict) -> tuple[float | None, float | None]:
        filled_raw = data.get("filledQty", data.get("filledQuantity", data.get("tradedQuantity")))
        average_raw = data.get("averageTradedPrice", data.get("avgTradedPrice", data.get("averagePrice", data.get("tradedPrice"))))
        filled = None if filled_raw in (None, "") else float(filled_raw)
        average = None if average_raw in (None, "") else float(average_raw)
        return filled, average
    def _validate_authoritative_order(self, data: dict, *, expected_order_id: str | None = None, expected_client_order_id: str | None = None) -> dict:
        if not isinstance(data, dict): raise RuntimeError("Dhan authoritative order must be an object")
        order_id = str(data.get("orderId") or "").strip()
        if not order_id: raise RuntimeError("Dhan authoritative order missing orderId")
        if expected_order_id is not None and order_id != str(expected_order_id).strip(): raise RuntimeError("Dhan broker order identity mismatch")
        correlation_id = data.get("correlationId")
        if expected_client_order_id is not None and (correlation_id is None or str(correlation_id).strip() != str(expected_client_order_id).strip()): raise RuntimeError("Dhan client order identity mismatch")
        broker_client_id = data.get("dhanClientId")
        if broker_client_id is not None and str(broker_client_id).strip() != self.config.client_id: raise RuntimeError("Dhan account identity mismatch")
        return data
    def _validate_trade_records(self, records: list[dict], *, expected_order_id: str | None = None) -> list[dict]:
        seen_trade_ids: set[str] = set()
        normalized: list[dict] = []
        for record in records:
            if not isinstance(record, dict): raise RuntimeError("Dhan trade response contains a non-object record")
            order_id = str(record.get("orderId") or "").strip()
            if not order_id: raise RuntimeError("Dhan trade response missing broker order identity")
            if expected_order_id is not None and order_id != expected_order_id: raise RuntimeError("Dhan trade response order identity does not match requested order")
            trade_id = str(record.get("exchangeTradeId") or "").strip()
            if not trade_id: raise RuntimeError("Dhan trade response missing trade identity")
            if trade_id in seen_trade_ids: raise RuntimeError("Dhan trade response contains duplicate trade identity")
            seen_trade_ids.add(trade_id)
            account_id = str(record.get("dhanClientId") or "").strip()
            if not account_id or account_id != self.config.client_id: raise RuntimeError("Dhan trade response account identity does not match configured account")
            try:
                quantity = float(record.get("tradedQuantity"))
                price = float(record.get("tradedPrice"))
            except (TypeError, ValueError):
                raise RuntimeError("Dhan trade response has invalid quantity or price") from None
            if quantity <= 0: raise RuntimeError("Dhan trade response requires positive traded quantity")
            if price <= 0: raise RuntimeError("Dhan trade response requires positive traded price")
            normalized.append(dict(record))
        return normalized
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderUpdate:
        self._require_live()
        if not request.security_id: raise ValueError("security_id is required for Dhan")
        correlation_id=request.client_order_id or uuid.uuid4().hex[:20]
        if len(correlation_id)>30: raise ValueError("Dhan correlationId must be at most 30 characters")
        payload={"dhanClientId":self.config.client_id,"correlationId":correlation_id,"transactionType":request.side.upper(),"exchangeSegment":request.exchange_segment,"productType":request.product_type,"orderType":request.order_type,"validity":request.validity,"securityId":request.security_id,"quantity":request.quantity,"price":request.price,"triggerPrice":request.trigger_price}
        response=self.transport.post(f"{self.config.base_url}/orders",headers=self._headers(),json=payload); response.raise_for_status(); data=self._validate_authoritative_order(response.json(), expected_client_order_id=correlation_id)
        status=self._placement_status(data.get("orderStatus"))
        if status not in {"NEW","PARTIALLY_FILLED","REJECTED","CANCELLED","FILLED"}: raise RuntimeError(f"unsupported Dhan placement status: {status}")
        filled, average = self._fill_fields(data)
        raw={"order_id":str(data["orderId"]),"status":status,"client_order_id":correlation_id,"symbol":request.symbol,"side":request.side.upper(),"quantity":request.quantity,"filled_quantity":filled,"average_price":average,"price":request.price,"broker_account_id":request.broker_account_id,"broker_route":request.broker_route,"broker_route_generation":request.broker_route_generation,"message":"DHAN_ORDER_ACCEPTED"}
        return normalize_broker_update(raw, expected=request)
    def find_order_by_client_id(self, client_order_id: str) -> dict | None:
        self._require_live()
        if not client_order_id or len(client_order_id)>30: raise ValueError("Dhan correlationId must be between 1 and 30 characters")
        response=self.transport.get(f"{self.config.base_url}/orders/external/{client_order_id}",headers=self._headers())
        if getattr(response,"status_code",None)==404: return None
        response.raise_for_status(); data=response.json(); return self._validate_authoritative_order(data, expected_client_order_id=client_order_id)
    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        self._require_live(); order_id=self._require_order_id(broker_order_id); response=self.transport.delete(f"{self.config.base_url}/orders/{order_id}",headers=self._headers()); response.raise_for_status(); data=self._validate_authoritative_order(response.json(), expected_order_id=order_id); return BrokerOrderUpdate(order_id=str(data["orderId"]),status=self._placement_status(data.get("orderStatus")),message="DHAN_CANCEL_RESULT")
    def get_order(self, broker_order_id: str) -> dict:
        self._require_live(); order_id=self._require_order_id(broker_order_id); response=self.transport.get(f"{self.config.base_url}/orders/{order_id}",headers=self._headers()); response.raise_for_status(); return self._validate_authoritative_order(response.json(), expected_order_id=order_id)
    def get_orders(self) -> list[dict]:
        self._require_live(); response=self.transport.get(f"{self.config.base_url}/orders",headers=self._headers()); response.raise_for_status(); data=response.json()
        if not isinstance(data,list): raise RuntimeError("Dhan orders response must be a list")
        validated=[]; seen=set()
        for order in data:
            item=self._validate_authoritative_order(order)
            order_id=str(item["orderId"])
            if order_id in seen: raise RuntimeError(f"duplicate Dhan broker order identity: {order_id}")
            seen.add(order_id); validated.append(item)
        return validated
    def get_order_snapshot(self):
        from app.broker_order_snapshot import BrokerOrderSnapshot
        return BrokerOrderSnapshot(orders=self.get_orders(), complete=True, source="dhan")
    def get_trades(self) -> list[dict]:
        self._require_live(); response=self.transport.get(f"{self.config.base_url}/trades",headers=self._headers()); response.raise_for_status(); data=response.json()
        if not isinstance(data,list): raise RuntimeError("Dhan trades response must be a list")
        return self._validate_trade_records(data)
    def get_trades_for_order(self, broker_order_id: str) -> list[dict]:
        self._require_live(); order_id=self._require_order_id(broker_order_id); response=self.transport.get(f"{self.config.base_url}/trades/{order_id}",headers=self._headers()); response.raise_for_status(); data=response.json()
        if not isinstance(data,list): raise RuntimeError("Dhan order-trades response must be a list")
        return self._validate_trade_records(data, expected_order_id=order_id)
    def get_positions(self) -> list[dict]:
        self._require_live(); response=self.transport.get(f"{self.config.base_url}/positions",headers=self._headers()); response.raise_for_status(); data=response.json()
        if not isinstance(data,list): raise RuntimeError("Dhan positions response must be a list")
        return data
    def get_position_snapshot(self) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(positions=self.get_positions(),complete=True,source="dhan")
    def get_account(self) -> dict:
        self._require_live(); response=self.transport.get(f"{self.config.base_url}/fundlimit",headers=self._headers()); response.raise_for_status(); return response.json()
    def get_snapshot(self) -> BrokerSnapshot: return dhan_snapshot(self.get_orders(), self.get_positions())
