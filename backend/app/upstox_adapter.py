from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
import httpx
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate, normalize_broker_update
from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_position_snapshot import BrokerPositionSnapshot

@dataclass(frozen=True)
class UpstoxConfig:
    access_token: str
    base_url: str = "https://api-hft.upstox.com"
    live_enabled: bool = False
    timeout_seconds: float = 10.0
    slice_orders: bool = False
    market_protection: int = -1
    broker_account_id: str | None = None
    broker_route: str | None = None
    broker_route_generation: str | None = None
    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0: raise ValueError("Upstox HTTP timeout must be greater than zero")
        if not (-1 <= self.market_protection <= 25): raise ValueError("Upstox market protection must be -1 or between 1 and 25")
        if self.slice_orders: raise ValueError("UPSTOX_SLICE is unsupported until child-order persistence is implemented")
        for value, field in ((self.broker_account_id, "broker_account_id"), (self.broker_route, "broker_route"), (self.broker_route_generation, "broker_route_generation")):
            if value is not None and not str(value).strip(): raise ValueError(f"Upstox {field} must be non-empty when configured")
    @classmethod
    def from_env(cls) -> "UpstoxConfig":
        return cls(access_token=os.getenv("UPSTOX_ACCESS_TOKEN", ""),base_url=os.getenv("UPSTOX_API_BASE_URL", "https://api-hft.upstox.com").rstrip("/"),live_enabled=os.getenv("UPSTOX_LIVE_ENABLED", "false").lower() == "true",timeout_seconds=float(os.getenv("UPSTOX_HTTP_TIMEOUT_SECONDS", "10")),slice_orders=os.getenv("UPSTOX_SLICE", "false").lower() == "true",market_protection=int(os.getenv("UPSTOX_MARKET_PROTECTION", "-1")))

class UpstoxHttpTransport:
    def __init__(self, timeout_seconds: float = 10.0, client: httpx.Client | None = None):
        if timeout_seconds <= 0: raise ValueError("Upstox HTTP timeout must be greater than zero")
        self.timeout_seconds = timeout_seconds; self.client = client or httpx.Client(timeout=timeout_seconds)
    def request(self, method: str, url: str, **kwargs): kwargs.setdefault("timeout", self.timeout_seconds); return self.client.request(method, url, **kwargs)
    def close(self) -> None: self.client.close()

class UpstoxAdapter(BrokerAdapter):
    name = "upstox"
    def __init__(self, config: UpstoxConfig | None = None, transport: Any | None = None): self.config = config or UpstoxConfig.from_env(); self.transport = transport or UpstoxHttpTransport(self.config.timeout_seconds)
    def _require_live(self) -> None:
        if not self.config.live_enabled: raise RuntimeError("UPSTOX_LIVE_ENABLED is false")
        if not self.config.access_token: raise RuntimeError("Upstox access token is not configured")
    def _headers(self) -> dict[str, str]: return {"Content-Type":"application/json","Accept":"application/json","Authorization":f"Bearer {self.config.access_token}"}
    @staticmethod
    def _validate_tag(client_order_id: str) -> str:
        if not client_order_id or len(client_order_id) > 40: raise ValueError("Upstox tag must be between 1 and 40 characters")
        return client_order_id
    @staticmethod
    def _validate_quantity(quantity: float) -> int:
        value = float(quantity)
        if not value.is_integer(): raise ValueError("Upstox order quantity must be an integer")
        if value <= 0: raise ValueError("Upstox order quantity must be positive")
        return int(value)
    @staticmethod
    def _validate_execution_contract(request: BrokerOrderRequest) -> None:
        if not str(request.security_id or "").strip():
            raise ValueError("Upstox security_id is required before submission")
        product = str(request.product_type or "").strip().upper()
        if product not in {"INTRADAY", "I", "CNC", "D", "MTF"}:
            raise ValueError(f"unsupported Upstox product_type: {request.product_type}")
        validity = str(request.validity or "").strip().upper()
        if validity not in {"DAY", "IOC"}:
            raise ValueError(f"unsupported Upstox validity: {request.validity}")
        exchange = str(request.exchange_segment or "").strip().upper()
        if exchange not in {"NSE_EQ", "NSE_FO", "BSE_EQ", "BSE_FO", "NCD_FO", "BCD_FO"}:
            raise ValueError(f"unsupported Upstox exchange_segment: {request.exchange_segment}")
    @staticmethod
    def _require_record_list(data: Any, context: str) -> list[dict[str, Any]]:
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data): raise RuntimeError(f"Upstox {context} is not an authoritative record list")
        return [dict(item) for item in data]
    @staticmethod
    def _require_record(data: Any, context: str) -> dict[str, Any]:
        if not isinstance(data, dict): raise RuntimeError(f"Upstox {context} is not an authoritative record")
        return dict(data)
    def _request_identity(self, request: BrokerOrderRequest) -> dict[str, str]:
        identity = {"broker_account_id": request.broker_account_id or self.config.broker_account_id,"broker_route": request.broker_route or self.config.broker_route,"broker_route_generation": request.broker_route_generation or self.config.broker_route_generation}
        for field, expected in (("broker_account_id", self.config.broker_account_id), ("broker_route", self.config.broker_route), ("broker_route_generation", self.config.broker_route_generation)):
            if expected is not None and identity[field] != expected: raise ValueError(f"Upstox {field} does not match configured route")
        return {k: str(v) for k, v in identity.items() if v is not None}
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderUpdate:
        self._require_live(); self._validate_execution_contract(request); tag=self._validate_tag(request.client_order_id); quantity=self._validate_quantity(request.quantity); order_type=request.order_type.upper()
        if order_type in {"MARKET","SL-M"} and not (-1 <= self.config.market_protection <= 25): raise ValueError("Upstox market protection must be -1 or between 1 and 25")
        payload={"quantity":quantity,"product":{"INTRADAY":"I","I":"I","CNC":"D","D":"D","MTF":"MTF"}.get(request.product_type.upper(),request.product_type.upper()),"validity":request.validity.upper(),"price":float(request.price or 0),"tag":tag,"instrument_token":request.security_id,"order_type":order_type,"transaction_type":request.side.upper(),"disclosed_quantity":0,"trigger_price":float(request.trigger_price or request.stop or 0),"is_amo":False,"slice":self.config.slice_orders}
        if order_type in {"MARKET","SL-M"}: payload["market_protection"]=self.config.market_protection
        response=self.transport.request("POST",f"{self.config.base_url}/v3/order/place",headers=self._headers(),json=payload); response.raise_for_status(); body=response.json(); data=body.get("data",body); order_ids=data.get("order_ids") or ([data.get("order_id")] if data.get("order_id") else [])
        if not order_ids: raise RuntimeError("Upstox placement response did not contain an order id")
        if len(order_ids)>1: raise RuntimeError("Upstox sliced order returned multiple broker order ids; child-order persistence is required")
        raw={"order_id":str(order_ids[0]),"status":"NEW","client_order_id":tag,"symbol":request.symbol,"side":request.side.upper(),"quantity":quantity,"price":request.price,"message":";".join(map(str,order_ids)),**self._request_identity(request)}
        return normalize_broker_update(raw, expected=request)
    def find_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        self._require_live(); tag=self._validate_tag(client_order_id); response=self.transport.request("GET",f"{self.config.base_url}/v2/order/history",headers=self._headers(),params={"tag":tag});
        if getattr(response,"status_code",None)==404: return None
        response.raise_for_status(); body=response.json(); data=body.get("data",body)
        if isinstance(data,dict): data=data.get("orders",[data])
        matches=[order for order in self._require_record_list(data, "order history response") if str(order.get("tag",tag))==tag]
        if not matches: return None
        if len(matches)==1: return matches[0]
        raise RuntimeError("ambiguous broker order identity")
    def get_order(self, broker_order_id: str) -> dict[str, Any]:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/order/details",headers=self._headers(),params={"order_id":broker_order_id}); response.raise_for_status(); body=response.json(); return self._require_record(body.get("data",body), "order response")
    def get_orders(self) -> list[dict[str, Any]]:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/order/retrieve-all",headers=self._headers()); response.raise_for_status(); body=response.json(); return self._require_record_list(body.get("data",body), "orders response")
    def get_order_snapshot(self) -> BrokerOrderSnapshot:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/order/retrieve-all",headers=self._headers()); response.raise_for_status(); body=response.json(); data=self._require_record_list(body.get("data",body), "order snapshot"); return BrokerOrderSnapshot(orders=data,complete=True,source="upstox")
    def get_trades_by_order(self, broker_order_id: str) -> list[dict[str, Any]]:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/order/trades",headers=self._headers(),params={"order_id":broker_order_id}); response.raise_for_status(); body=response.json(); data=self._require_record_list(body.get("data",body), "trades response")
        if any(str(trade.get("order_id", broker_order_id)) != str(broker_order_id) for trade in data):
            raise RuntimeError("Upstox trades response contains a mismatched broker order identity")
        return data
    def cancel_order(self, broker_order_id: str) -> BrokerOrderUpdate:
        self._require_live(); response=self.transport.request("DELETE",f"{self.config.base_url}/v3/order/cancel",headers=self._headers(),params={"order_id":broker_order_id}); response.raise_for_status(); body=response.json(); data=self._require_record(body.get("data",body), "cancel response"); raw={"order_id":str(data.get("order_id",broker_order_id)),"status":"CANCELLED","message":str(data.get("message","")) or None,**{k:v for k,v in (("broker_account_id",self.config.broker_account_id),("broker_route",self.config.broker_route),("broker_route_generation",self.config.broker_route_generation)) if v is not None}}; return normalize_broker_update(raw)
    def get_positions(self) -> list[dict[str, Any]]:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/portfolio/short-term-positions",headers=self._headers()); response.raise_for_status(); body=response.json(); return self._require_record_list(body.get("data",body), "positions response")
    def get_position_snapshot(self) -> BrokerPositionSnapshot:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/portfolio/short-term-positions",headers=self._headers()); response.raise_for_status(); body=response.json(); data=self._require_record_list(body.get("data",body), "position snapshot"); return BrokerPositionSnapshot(positions=data,complete=True,source="upstox")
    def get_account(self) -> dict[str, Any]:
        self._require_live(); response=self.transport.request("GET",f"{self.config.base_url}/v2/user/get-funds-and-margin",headers=self._headers()); response.raise_for_status(); body=response.json(); return self._require_record(body.get("data",body), "account response")
