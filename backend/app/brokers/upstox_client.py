from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class UpstoxAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class UpstoxClient:
    """Bounded Upstox REST client; secrets are never included in exceptions."""

    API_BASE = "https://api.upstox.com/v2"
    HFT_BASE = "https://api-hft.upstox.com/v3"

    def __init__(self, access_token: str, timeout: float = 10.0):
        if not access_token or not access_token.strip():
            raise ValueError("Upstox access token is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.access_token = access_token.strip()
        self.timeout = timeout

    def _request(self, method: str, base: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
        query = f"?{urlencode({k: v for k, v in (params or {}).items() if v is not None})}" if params else ""
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{base}{path}{query}",
            data=data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            raise UpstoxAPIError("Upstox API request failed", status_code=exc.code, payload=payload) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise UpstoxAPIError("Upstox API network request failed") from exc

    @staticmethod
    def _data(response: Any) -> Any:
        if isinstance(response, dict) and response.get("status") not in (None, "success"):
            raise UpstoxAPIError("Upstox returned an unsuccessful response", payload=response)
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return response

    def get_profile(self) -> dict[str, Any]:
        data = self._data(self._request("GET", self.API_BASE, "/user/profile"))
        return data if isinstance(data, dict) else {"data": data}

    def get_quote(self, instrument_key: str) -> dict[str, Any]:
        if not instrument_key:
            raise ValueError("instrument_key is required")
        data = self._data(self._request("GET", self.API_BASE, "/market-quote/quotes", params={"instrument_key": instrument_key}))
        return data if isinstance(data, dict) else {"data": data}

    def get_positions(self) -> list[dict[str, Any]]:
        data = self._data(self._request("GET", self.API_BASE, "/portfolio/short-term-positions"))
        return data if isinstance(data, list) else []

    def get_orders(self) -> list[dict[str, Any]]:
        data = self._data(self._request("GET", self.API_BASE, "/order/retrieve-all"))
        return data if isinstance(data, list) else []

    def get_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")
        data = self._data(self._request("GET", self.API_BASE, "/order/details", params={"order_id": order_id}))
        return data if isinstance(data, dict) else {"data": data}

    def get_trades(self) -> list[dict[str, Any]]:
        data = self._data(self._request("GET", self.API_BASE, "/order/trades/get-trades-for-day"))
        return data if isinstance(data, list) else []

    def get_trades_for_order(self, order_id: str) -> list[dict[str, Any]]:
        if not order_id:
            raise ValueError("order_id is required")
        data = self._data(self._request("GET", self.API_BASE, "/order/trades", params={"order_id": order_id}))
        return data if isinstance(data, list) else []

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(order, dict) or not order:
            raise ValueError("order must be a non-empty mapping")
        data = self._data(self._request("POST", self.HFT_BASE, "/order/place", body=order))
        return data if isinstance(data, dict) else {"data": data}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")
        data = self._data(self._request("DELETE", self.HFT_BASE, "/order/cancel", params={"order_id": order_id}))
        return data if isinstance(data, dict) else {"data": data}

    def health(self) -> dict[str, Any]:
        self.get_profile()
        return {"broker": "upstox", "authenticated": True}
