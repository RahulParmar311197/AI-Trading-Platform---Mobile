from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.order_lifecycle import OrderLifecycle, OrderStatus


@dataclass(frozen=True)
class ReconciliationMismatch:
    domain: str
    identity: str
    reason: str


def _signed_position(side: str, quantity: float) -> float:
    side = str(side).upper()
    if side in {"BUY", "LONG"}:
        return float(quantity)
    if side in {"SELL", "SHORT"}:
        return -float(quantity)
    raise ValueError(f"invalid position side: {side}")


def compare_broker_state(
    lifecycle: OrderLifecycle,
    *,
    broker_orders: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]],
) -> list[ReconciliationMismatch]:
    mismatches: list[ReconciliationMismatch] = []

    local_orders = {
        str(order.broker_order_id): order
        for order in lifecycle.orders.values()
        if order.broker_order_id
        and order.status not in (OrderStatus.CANCELLED, OrderStatus.REJECTED)
    }
    broker_by_id: dict[str, dict[str, Any]] = {}
    for raw in broker_orders:
        broker_id = raw.get("order_id", raw.get("broker_order_id"))
        if broker_id is None:
            mismatches.append(ReconciliationMismatch("orders", "<missing>", "broker order has no broker order ID"))
            continue
        key = str(broker_id)
        if key in broker_by_id:
            mismatches.append(ReconciliationMismatch("orders", key, "duplicate broker order ID"))
        broker_by_id[key] = raw

    for broker_id, local in local_orders.items():
        broker = broker_by_id.get(broker_id)
        if broker is None:
            mismatches.append(ReconciliationMismatch("orders", broker_id, "local active order missing at broker"))
            continue
        broker_symbol = str(broker.get("symbol", "")).upper()
        if broker_symbol and broker_symbol != local.symbol.upper():
            mismatches.append(ReconciliationMismatch("orders", broker_id, "symbol mismatch"))
        broker_side = str(broker.get("side", "")).upper()
        if broker_side and broker_side != local.side.upper():
            mismatches.append(ReconciliationMismatch("orders", broker_id, "side mismatch"))

    for broker_id, broker in broker_by_id.items():
        if broker_id not in local_orders:
            status = str(broker.get("status", "")).upper()
            if status not in {"CANCELLED", "REJECTED", "FILLED"}:
                mismatches.append(ReconciliationMismatch("orders", broker_id, "unowned active broker order"))

    local_positions = {str(symbol).upper(): position for symbol, position in lifecycle.positions.items() if position.quantity > 0}
    broker_position_totals: dict[str, float] = {}
    for raw in broker_positions:
        symbol = str(raw.get("symbol", raw.get("trading_symbol", ""))).upper()
        if not symbol:
            mismatches.append(ReconciliationMismatch("positions", "<missing>", "broker position has no symbol"))
            continue
        quantity = raw.get("quantity", raw.get("net_quantity", raw.get("netQty", 0)))
        side = raw.get("side")
        try:
            signed = _signed_position(side, float(quantity)) if side is not None else float(quantity)
        except (TypeError, ValueError) as exc:
            mismatches.append(ReconciliationMismatch("positions", symbol, str(exc)))
            continue
        broker_position_totals[symbol] = broker_position_totals.get(symbol, 0.0) + signed

    symbols = set(local_positions) | set(broker_position_totals)
    for symbol in sorted(symbols):
        local = local_positions.get(symbol)
        local_signed = 0.0 if local is None else _signed_position(local.side, local.quantity)
        broker_signed = broker_position_totals.get(symbol, 0.0)
        if abs(local_signed - broker_signed) > 1e-9:
            mismatches.append(ReconciliationMismatch("positions", symbol, f"local={local_signed} broker={broker_signed}"))

    return mismatches
