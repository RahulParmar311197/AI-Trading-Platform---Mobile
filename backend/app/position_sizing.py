from __future__ import annotations


def size_position(equity: float, risk_percent: float, entry: float, stop_loss: float, max_quantity: float | None = None) -> dict:
    if equity <= 0 or risk_percent <= 0 or entry <= 0 or stop_loss <= 0:
        raise ValueError("equity, risk_percent, entry and stop_loss must be positive")
    risk_amount = equity * risk_percent / 100
    per_unit_risk = abs(entry - stop_loss)
    if per_unit_risk == 0:
        raise ValueError("entry and stop loss cannot be equal")
    quantity = risk_amount / per_unit_risk
    if max_quantity is not None:
        quantity = min(quantity, max_quantity)
    return {
        "risk_amount": risk_amount,
        "per_unit_risk": per_unit_risk,
        "quantity": quantity,
        "notional": quantity * entry,
    }
