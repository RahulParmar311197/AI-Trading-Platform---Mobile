from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def _finite_number(value: Any, *, field: str, default: float | None = None) -> float:
    if value is None or value == "":
        if default is not None:
            return default
        raise ValueError(f"{field} is required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"invalid {field}: non-finite value")
    return number


def order_identity(order: dict[str, Any]) -> str:
    if not isinstance(order, dict):
        raise ValueError("reconciliation order must be an object")
    identity = str(
        order.get("client_order_id")
        or order.get("order_id")
        or order.get("broker_order_id")
        or ""
    ).strip()
    if not identity:
        raise ValueError("reconciliation order is missing a stable identity")
    return identity


def validate_orders(orders: Iterable[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    identities: set[str] = set()
    for order in orders:
        identity = order_identity(order)
        if identity in identities:
            raise ValueError(f"duplicate {source} order identity: {identity}")
        identities.add(identity)
        quantity = _finite_number(
            order.get("quantity", order.get("requested_quantity")),
            field=f"{source} order quantity",
            default=0.0,
        )
        filled = _finite_number(
            order.get("filled_quantity", order.get("filledQty", order.get("filled_qty"))),
            field=f"{source} order filled quantity",
            default=0.0,
        )
        if quantity < 0 or filled < 0:
            raise ValueError(f"negative {source} order quantity")
        if filled > quantity + 1e-9:
            raise ValueError(f"{source} order filled quantity exceeds quantity: {identity}")
        validated.append(dict(order))
    return validated


def validate_positions(positions: Iterable[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for position in positions:
        if not isinstance(position, dict):
            raise ValueError(f"{source} position must be an object")
        symbol = str(position.get("symbol") or position.get("trading_symbol") or "").strip().upper()
        if not symbol:
            raise ValueError(f"{source} position is missing symbol")
        if symbol in symbols:
            raise ValueError(f"duplicate {source} position symbol: {symbol}")
        symbols.add(symbol)
        quantity = _finite_number(
            position.get("signed_quantity", position.get("quantity", position.get("net_quantity", position.get("netQty")))),
            field=f"{source} position quantity",
            default=0.0,
        )
        if "side" in position and abs(quantity) > 1e-9:
            side = str(position.get("side") or "").strip().upper()
            if side not in {"BUY", "SELL", "B", "S", "LONG", "SHORT", "1", "-1", "+1"}:
                raise ValueError(f"unknown {source} position side: {position.get('side')}")
        validated.append(dict(position))
    return validated


def validate_reconciliation_inputs(
    internal_orders: Iterable[dict[str, Any]],
    broker_orders: Iterable[dict[str, Any]],
    internal_positions: Iterable[dict[str, Any]],
    broker_positions: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate all reconciliation inputs before comparison; callers should halt on failure."""
    return (
        validate_orders(internal_orders, source="internal"),
        validate_orders(broker_orders, source="broker"),
        validate_positions(internal_positions, source="internal"),
        validate_positions(broker_positions, source="broker"),
    )
