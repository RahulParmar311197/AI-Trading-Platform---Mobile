import json
import urllib.parse
import urllib.request
from typing import Any

class UpstoxClient:
    """Small authenticated REST client for read-only Upstox connectivity."""
    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, access_token: str, timeout: float = 10.0):
        if not access_token:
            raise ValueError("Upstox access token is required")
        self.access_token = access_token
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(f"{self.BASE_URL}{path}{query}", headers={"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_profile(self) -> dict[str, Any]:
        return self._get("/user/profile/full")

    def get_positions(self) -> dict[str, Any]:
        return self._get("/portfolio/short-term-positions")

    def get_holdings(self) -> dict[str, Any]:
        return self._get("/portfolio/long-term-holdings")

    def health(self) -> dict[str, Any]:
        self.get_profile()
        return {"broker": "upstox", "authenticated": True}
