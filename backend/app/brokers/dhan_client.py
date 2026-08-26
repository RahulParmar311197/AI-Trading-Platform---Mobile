from typing import Any

import httpx


class DhanClient:
    """Authenticated DhanHQ v2 REST client.

    This client intentionally contains no credentials of its own beyond the
    short-lived access token supplied by the broker-account service.
    Live order submission remains disabled until the execution gate enables it.
    """

    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self, access_token: str, timeout: float = 10.0):
        if not access_token:
            raise ValueError("Dhan access token is required")
        self.access_token = access_token
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": self.access_token,
            **headers,
        }
        with httpx.Client(base_url=self.BASE_URL, timeout=self.timeout) as client:
            response = client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

    def get_positions(self) -> Any:
        return self._request("GET", "/positions")

    def get_fund_limits(self) -> Any:
        return self._request("GET", "/fundlimit")

    def get_orders(self) -> Any:
        return self._request("GET", "/orders")

    def get_order(self, order_id: str) -> Any:
        return self._request("GET", f"/orders/{order_id}")

    def get_order_by_correlation_id(self, correlation_id: str) -> Any:
        return self._request("GET", f"/orders/external/{correlation_id}")

    def get_trades(self) -> Any:
        return self._request("GET", "/trades")

    def get_trades_for_order(self, order_id: str) -> Any:
        return self._request("GET", f"/trades/{order_id}")

    def health(self) -> dict[str, Any]:
        self.get_fund_limits()
        return {"broker": "dhan", "authenticated": True}
