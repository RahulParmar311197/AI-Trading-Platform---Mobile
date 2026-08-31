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
    DATA_BASE = "https://api.upstox.com/v3"
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

    @classmethod
    def _object_data(cls, response: Any, operation: str) -> dict[str, Any]:
        data = cls._data(response)
        if not isinstance(data, dict):
            raise UpstoxAPIError(f"Upstox {operation} response has invalid object data", payload=response)
        return data

    @classmethod
    def _list_data(cls, response: Any, operation: str) -> list[dict[str, Any]]:
        data = cls._data(response)
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise UpstoxAPIError(f"Upstox {operation} response has invalid list data", payload=response)
        return data

    def get_profile(self) -> dict[str, Any]:
        return self._object_data(self._request("GET", self.API_BASE, "/user/profile"), "profile")

    def get_quote(self, instrument_key: str) -> dict[str, Any]:
        if not instrument_key:
            raise ValueError("instrument_key is required")
        return self._object_data(
            self._request("GET", self.API_BASE, "/market-quote/quotes", params={"instrument_key": instrument_key}),
            "quote",
        )

    def get_historical_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        to_date: str,
        from_date: str | None = None,
    ) -> list[list[Any]]:
        """Fetch Upstox Historical Candle V3 rows without inventing provider fields."""
        if not instrument_key.strip():
            raise ValueError("instrument_key is required")
        if unit not in {"minutes", "hours", "days", "weeks", "months"}:
            raise ValueError("unit must be minutes, hours, days, weeks, or months")
        if interval <= 0:
            raise ValueError("interval must be positive")
        if not to_date:
            raise ValueError("to_date is required")
        if from_date is not None and not from_date:
            raise ValueError("from_date must be omitted or a non-empty date")
        data = self._data(
            self._request(
                "GET",
                self.DATA_BASE,
                f"/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}"
                + (f"/{from_date}" if from_date else ""),
            )
        )
        if not isinstance(data, dict) or not isinstance(data.get("candles"), list):
            raise UpstoxAPIError("Upstox historical-candle response has invalid candle data", payload=data)
        return data["candles"]

    def get_positions(self) -> list[dict[str, Any]]:
        return self._list_data(self._request("GET", self.API_BASE, "/portfolio/short-term-positions"), "positions")

    def get_orders(self) -> list[dict[str, Any]]:
        return self._list_data(self._request("GET", self.API_BASE, "/order/retrieve-all"), "orders")

    def get_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")
        return self._object_data(
            self._request("GET", self.API_BASE, "/order/details", params={"order_id": order_id}),
            "order",
        )

    def get_trades(self) -> list[dict[str, Any]]:
        return self._list_data(self._request("GET", self.API_BASE, "/order/trades/get-trades-for-day"), "trades")

    def get_trades_for_order(self, order_id: str) -> list[dict[str, Any]]:
        if not order_id:
            raise ValueError("order_id is required")
        return self._list_data(
            self._request("GET", self.API_BASE, "/order/trades", params={"order_id": order_id}),
            "order trades",
        )

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(order, dict) or not order:
            raise ValueError("order must be a non-empty mapping")
        return self._object_data(self._request("POST", self.HFT_BASE, "/order/place", body=order), "place-order")

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise ValueError("order_id is required")
        return self._object_data(
            self._request("DELETE", self.HFT_BASE, "/order/cancel", params={"order_id": order_id}),
            "cancel-order",
        )

    def health(self) -> dict[str, Any]:
        self.get_profile()
        return {"broker": "upstox", "authenticated": True}
