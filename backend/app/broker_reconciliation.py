from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class PositionDelta:
    symbol: str
    local_quantity: float
    broker_quantity: float
    delta: float


@dataclass(frozen=True)
class ReconciliationReport:
    matched: bool
    deltas: tuple[PositionDelta, ...]
    broker_only: tuple[str, ...]
    local_only: tuple[str, ...]


@dataclass(frozen=True)
class LocalOrderSnapshot:
    broker_order_id: str
    symbol: str
    side: str
    quantity: float
    filled_quantity: float
    status: str


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    broker_order_id: str
    symbol: str
    side: str
    quantity: float
    filled_quantity: float
    status: str


@dataclass(frozen=True)
class ReconciliationIssue:
    broker_order_id: str
    field: str
    local_value: Any
    broker_value: Any
    message: str


_STATUS_ALIASES = {
    "NEW": "OPEN",
    "PENDING": "OPEN",
    "SUBMITTED": "OPEN",
    "OPEN": "OPEN",
    "PARTIAL": "PARTIALLY_FILLED",
    "PARTIALLY_FILLED": "PARTIALLY_FILLED",
    "PARTIALLY FILLED": "PARTIALLY_FILLED",
    "FILLED": "FILLED",
    "COMPLETE": "FILLED",
    "COMPLETED": "FILLED",
    "CANCELLED": "CANCELLED",
    "CANCELED": "CANCELLED",
    "REJECTED": "REJECTED",
}

# The broker is allowed to advance an order through these lifecycle states.
# Terminal states must never regress. A status mismatch that is not an allowed
# transition is treated as malformed/unsafe broker state and fails closed.
_ALLOWED_STATUS_TRANSITIONS = {
    "OPEN": {"OPEN", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"},
    "PARTIALLY_FILLED": {"PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"},
    "FILLED": {"FILLED"},
    "CANCELLED": {"CANCELLED"},
    "REJECTED": {"REJECTED"},
}


def _canonical_order_status(value: Any, *, order_id: str) -> str:
    status = str(value).strip().upper()
    canonical = _STATUS_ALIASES.get(status)
    if canonical is None:
        raise ValueError(f"order {order_id} has unsupported status")
    return canonical


def _finite_non_negative(value: Any, *, field: str, order_id: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"order {order_id} has invalid {field}") from exc
    if not isfinite(number):
        raise ValueError(f"order {order_id} has non-finite {field}")
    if number < 0:
        raise ValueError(f"order {order_id} has negative {field}")
    return number


def _validate_order_snapshot(order: LocalOrderSnapshot | BrokerOrderSnapshot, *, source: str) -> tuple[str, str]:
    order_id = str(order.broker_order_id).strip()
    if not order_id:
        raise ValueError(f"{source} order is missing broker_order_id")
    symbol = str(order.symbol).strip()
    if not symbol:
        raise ValueError(f"order {order_id} is missing symbol")
    side = str(order.side).strip().upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"order {order_id} has invalid side")
    status = _canonical_order_status(order.status, order_id=order_id)
    quantity = _finite_non_negative(order.quantity, field="quantity", order_id=order_id)
    filled_quantity = _finite_non_negative(order.filled_quantity, field="filled_quantity", order_id=order_id)
    if filled_quantity > quantity:
        raise ValueError(f"order {order_id} has filled_quantity greater than quantity")

    if status == "OPEN" and filled_quantity != 0:
        raise ValueError(f"order {order_id} has OPEN status with non-zero filled_quantity")
    if status == "PARTIALLY_FILLED" and not (0 < filled_quantity < quantity):
        raise ValueError(f"order {order_id} has PARTIALLY_FILLED status with invalid filled_quantity")
    if status == "FILLED" and filled_quantity != quantity:
        raise ValueError(f"order {order_id} has FILLED status with incomplete filled_quantity")
    if status == "REJECTED" and filled_quantity != 0:
        raise ValueError(f"order {order_id} has REJECTED status with non-zero filled_quantity")
    # A cancelled order may have filled partially before cancellation.
    return order_id, status


def _validate_status_transition(*, order_id: str, local_status: str, broker_status: str) -> None:
    allowed = _ALLOWED_STATUS_TRANSITIONS[local_status]
    if broker_status not in allowed:
        raise ValueError(
            f"order {order_id} has unsafe status regression: "
            f"{local_status} -> {broker_status}"
        )


class OrderReconciler:
    """Compare persisted local order truth with broker order truth."""

    def __init__(self, *, quantity_tolerance: float = 0.0) -> None:
        if not isfinite(quantity_tolerance) or quantity_tolerance < 0:
            raise ValueError("quantity_tolerance must be finite and non-negative")
        self.quantity_tolerance = float(quantity_tolerance)

    def reconcile(
        self,
        local_orders: Mapping[str, LocalOrderSnapshot],
        broker_orders: list[BrokerOrderSnapshot],
    ) -> list[ReconciliationIssue]:
        issues: list[ReconciliationIssue] = []
        broker_by_id: dict[str, BrokerOrderSnapshot] = {}
        broker_status_by_id: dict[str, str] = {}
        for broker in broker_orders:
            broker_id, broker_status = _validate_order_snapshot(broker, source="broker")
            if broker_id in broker_by_id:
                issues.append(ReconciliationIssue(broker_id, "broker_order_id", broker_id, broker_id, "duplicate broker order identity"))
                continue
            broker_by_id[broker_id] = broker
            broker_status_by_id[broker_id] = broker_status

        for key, local in local_orders.items():
            broker_id, local_status = _validate_order_snapshot(local, source="local")
            fallback_id = str(key).strip()
            if fallback_id and broker_id != fallback_id:
                issues.append(ReconciliationIssue(broker_id, "broker_order_id", fallback_id, broker_id, "local order key does not match broker order identity"))
            broker = broker_by_id.pop(broker_id, None)
            broker_status = broker_status_by_id.pop(broker_id, None)
            if broker is None:
                issues.append(ReconciliationIssue(broker_id, "order", local_status, None, "local order is missing at broker"))
                continue
            if str(local.symbol).strip() != str(broker.symbol).strip():
                issues.append(ReconciliationIssue(broker_id, "symbol", local.symbol, broker.symbol, "order symbol mismatch"))
            if str(local.side).upper() != str(broker.side).upper():
                issues.append(ReconciliationIssue(broker_id, "side", local.side, broker.side, "order side mismatch"))
            if abs(float(local.quantity) - float(broker.quantity)) > self.quantity_tolerance:
                issues.append(ReconciliationIssue(broker_id, "quantity", local.quantity, broker.quantity, "order quantity mismatch"))
            if abs(float(local.filled_quantity) - float(broker.filled_quantity)) > self.quantity_tolerance:
                issues.append(ReconciliationIssue(broker_id, "filled_quantity", local.filled_quantity, broker.filled_quantity, "filled quantity mismatch"))
            assert broker_status is not None
            _validate_status_transition(order_id=broker_id, local_status=local_status, broker_status=broker_status)
            if local_status != broker_status:
                issues.append(ReconciliationIssue(broker_id, "status", local.status, broker.status, "order status mismatch"))

        for broker_id in sorted(broker_by_id):
            issues.append(ReconciliationIssue(broker_id, "order", None, broker_by_id[broker_id].status, "broker order is missing locally"))
        return issues


def _normalise(rows: list[dict[str, Any]], symbol_key: str = "symbol", qty_key: str = "quantity") -> dict[str, float]:
    result: dict[str, float] = {}
    for index, row in enumerate(rows):
        symbol = str(row.get(symbol_key, "")).strip()
        if not symbol:
            raise ValueError(f"position row {index} is missing symbol")
        if qty_key not in row or row[qty_key] is None:
            raise ValueError(f"position row {index} is missing quantity")
        try:
            quantity = float(row[qty_key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"position row {index} has invalid quantity") from exc
        if not isfinite(quantity):
            raise ValueError(f"position row {index} has non-finite quantity")
        result[symbol] = result.get(symbol, 0.0) + quantity
    return result


def reconcile_positions(
    local_positions: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]],
    *,
    quantity_tolerance: float = 0.0,
) -> ReconciliationReport:
    """Compare local and broker positions without mutating either source."""
    if not isfinite(quantity_tolerance) or quantity_tolerance < 0:
        raise ValueError("quantity_tolerance must be finite and non-negative")

    local = _normalise(local_positions)
    broker = _normalise(broker_positions)
    symbols = set(local) | set(broker)
    deltas: list[PositionDelta] = []

    for symbol in sorted(symbols):
        lq = local.get(symbol, 0.0)
        bq = broker.get(symbol, 0.0)
        delta = bq - lq
        if not isfinite(lq) or not isfinite(bq):
            deltas.append(PositionDelta(symbol, lq, bq, delta))
        elif abs(delta) > quantity_tolerance:
            deltas.append(PositionDelta(symbol, lq, bq, delta))

    return ReconciliationReport(
        matched=not deltas,
        deltas=tuple(deltas),
        broker_only=tuple(sorted(set(broker) - set(local))),
        local_only=tuple(sorted(set(local) - set(broker))),
    )
