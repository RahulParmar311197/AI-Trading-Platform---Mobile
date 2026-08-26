from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def _normalise(rows: list[dict[str, Any]], symbol_key: str = "symbol", qty_key: str = "quantity") -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        symbol = str(row.get(symbol_key, "")).strip()
        if not symbol:
            continue
        quantity = float(row.get(qty_key, 0) or 0)
        result[symbol] = result.get(symbol, 0.0) + quantity
    return result


def reconcile_positions(
    local_positions: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]],
    *,
    quantity_tolerance: float = 0.0,
) -> ReconciliationReport:
    """Compare local and broker positions without mutating either source."""
    if quantity_tolerance < 0:
        raise ValueError("quantity_tolerance cannot be negative")

    local = _normalise(local_positions)
    broker = _normalise(broker_positions)
    symbols = set(local) | set(broker)
    deltas: list[PositionDelta] = []

    for symbol in sorted(symbols):
        lq = local.get(symbol, 0.0)
        bq = broker.get(symbol, 0.0)
        delta = bq - lq
        if abs(delta) > quantity_tolerance:
            deltas.append(PositionDelta(symbol, lq, bq, delta))

    return ReconciliationReport(
        matched=not deltas,
        deltas=tuple(deltas),
        broker_only=tuple(sorted(set(broker) - set(local))),
        local_only=tuple(sorted(set(local) - set(broker))),
    )
