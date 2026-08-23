from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True)
class PositionSize:
    quantity: int
    risk_amount: float
    risk_per_unit: float
    notional: float


def calculate_position_size(
    *,
    equity: float,
    risk_percent: float,
    entry: float,
    stop: float,
    lot_size: int = 1,
    max_notional_percent: float | None = None,
) -> PositionSize:
    values = (equity, risk_percent, entry, stop)
    if not all(isfinite(v) for v in values):
        raise ValueError("risk sizing inputs must be finite")
    if equity <= 0 or risk_percent <= 0 or entry <= 0:
        raise ValueError("equity, risk_percent and entry must be positive")
    if entry == stop:
        raise ValueError("entry and stop must differ")
    if lot_size < 1:
        raise ValueError("lot_size must be positive")
    if max_notional_percent is not None and max_notional_percent <= 0:
        raise ValueError("max_notional_percent must be positive")

    risk_per_unit = abs(entry - stop)
    risk_budget = equity * risk_percent / 100.0
    quantity = floor(risk_budget / risk_per_unit / lot_size) * lot_size

    if max_notional_percent is not None:
        notional_cap = equity * max_notional_percent / 100.0
        max_quantity = floor(notional_cap / entry / lot_size) * lot_size
        quantity = min(quantity, max_quantity)

    return PositionSize(
        quantity=quantity,
        risk_amount=quantity * risk_per_unit,
        risk_per_unit=risk_per_unit,
        notional=quantity * entry,
    )
