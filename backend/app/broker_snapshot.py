from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from time import time
from typing import Any


@dataclass(frozen=True)
class BrokerSnapshot:
    orders: list[dict[str, Any]]
    positions: list[dict[str, Any]]
    fetched_at: float = field(default_factory=time)
    broker_route: str | None = None
    broker_account_id: int | None = None

    def fingerprint(self) -> str:
        """Return a deterministic identity for broker state used by risk authorization."""
        def canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), default=str))

        payload = {
            "broker_route": self.broker_route,
            "broker_account_id": self.broker_account_id,
            "orders": canonical_rows(self.orders),
            "positions": canonical_rows(self.positions),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode("utf-8")).hexdigest()


def canonical_order_status(status: Any) -> str:
    value = str(status or "").upper()
    return {
        "TRADED": "FILLED",
        "FILLED": "FILLED",
        "CANCELLED": "CANCELLED",
        "REJECTED": "REJECTED",
        "TRANSIT": "NEW",
        "PENDING": "NEW",
    }.get(value, value)


def map_dhan_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "broker_order_id": str(row.get("orderId") or row.get("order_id") or ""),
        "client_order_id": row.get("correlationId") or row.get("client_order_id"),
        "status": canonical_order_status(row.get("orderStatus") or row.get("status")),
    }


def map_dhan_position(row: dict[str, Any]) -> dict[str, Any]:
    symbol = row.get("tradingSymbol") or row.get("symbol") or row.get("securityId")
    quantity = row.get("netQty", row.get("quantity", 0))
    return {
        "symbol": str(symbol or "").upper(),
        "quantity": float(quantity or 0),
    }


def dhan_snapshot(orders: list[dict[str, Any]], positions: list[dict[str, Any]]) -> BrokerSnapshot:
    return BrokerSnapshot(
        orders=[map_dhan_order(row) for row in orders],
        positions=[map_dhan_position(row) for row in positions],
    )
