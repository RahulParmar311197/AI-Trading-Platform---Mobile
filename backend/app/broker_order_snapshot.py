from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    """Broker order snapshot with an explicit completeness/authority contract."""

    orders: list[dict[str, Any]]
    complete: bool
    source: str = "broker"
    as_of: float | None = None

    def require_authoritative(self) -> list[dict[str, Any]]:
        if not self.complete:
            raise RuntimeError("broker order snapshot is not authoritative")
        if not isinstance(self.orders, list):
            raise RuntimeError("broker order snapshot is invalid")
        return self.orders
