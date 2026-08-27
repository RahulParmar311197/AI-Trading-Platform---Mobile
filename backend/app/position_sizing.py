from __future__ import annotations

from dataclasses import dataclass
import math

from app.instruments import InstrumentSpec


@dataclass(frozen=True)
class PositionSize:
    quantity: int
    risk_budget: float
    risk_per_unit: float
    stop_distance: float


def calculate_position_size(*, equity: float, risk_fraction: float, entry: float, stop: float, instrument: InstrumentSpec, max_quantity: int | None = None) -> PositionSize:
    """Calculate quantity from account risk and stop distance; fail closed on invalid inputs."""
    values = (equity, risk_fraction, entry, stop, instrument.multiplier)
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("position sizing inputs must be finite")
    if equity <= 0 or not 0 < risk_fraction <= 1:
        raise ValueError("equity must be positive and risk_fraction must be in (0, 1]")
    if entry <= 0 or stop <= 0 or entry == stop:
        raise ValueError("entry and stop must be positive and different")
    if not instrument.tradable:
        raise ValueError("instrument is not tradable")
    if instrument.lot_size <= 0 or instrument.multiplier <= 0:
        raise ValueError("invalid instrument sizing metadata")
    if max_quantity is not None and max_quantity < instrument.lot_size:
        raise ValueError("max_quantity is below one lot")
    stop_distance = abs(entry - stop)
    risk_per_unit = stop_distance * instrument.multiplier
    risk_budget = equity * risk_fraction
    lots = math.floor(risk_budget / (risk_per_unit * instrument.lot_size))
    quantity = lots * instrument.lot_size
    if max_quantity is not None:
        quantity = min(quantity, (max_quantity // instrument.lot_size) * instrument.lot_size)
    if quantity < instrument.lot_size:
        raise ValueError("risk budget is insufficient for one lot")
    return PositionSize(quantity, risk_budget, risk_per_unit, stop_distance)


def size_position(equity: float, risk_percent: float, entry: float, stop_loss: float, max_quantity: float | None = None) -> dict:
    """Backward-compatible share sizing for callers not yet migrated to InstrumentSpec."""
    if equity <= 0 or risk_percent <= 0 or entry <= 0 or stop_loss <= 0:
        raise ValueError("equity, risk_percent, entry and stop_loss must be positive")
    risk_amount = equity * risk_percent / 100
    per_unit_risk = abs(entry - stop_loss)
    if per_unit_risk == 0:
        raise ValueError("entry and stop loss cannot be equal")
    quantity = risk_amount / per_unit_risk
    if max_quantity is not None:
        quantity = min(quantity, max_quantity)
    return {"risk_amount": risk_amount, "per_unit_risk": per_unit_risk, "quantity": quantity, "notional": quantity * entry}
