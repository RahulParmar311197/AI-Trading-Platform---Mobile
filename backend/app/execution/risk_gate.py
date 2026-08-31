from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_quantity: float
    max_notional: float


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskGate:
    """Deterministic pre-trade authorization gate."""

    def __init__(self, limits: RiskLimits):
        if limits.max_quantity <= 0 or limits.max_notional <= 0:
            raise ValueError("risk limits must be positive")
        self._limits = limits

    def authorize(self, *, quantity: float, price: float | None, order_type: str) -> RiskDecision:
        if quantity <= 0:
            return RiskDecision(False, "quantity must be positive")
        if quantity > self._limits.max_quantity:
            return RiskDecision(False, "quantity exceeds risk limit")
        if order_type.upper() != "MARKET" and (price is None or price <= 0):
            return RiskDecision(False, "limit/stop order requires positive price")
        if price is not None and price < 0:
            return RiskDecision(False, "price must not be negative")
        notional = quantity * (price or 0.0)
        if price is not None and notional > self._limits.max_notional:
            return RiskDecision(False, "notional exceeds risk limit")
        return RiskDecision(True, "approved")
