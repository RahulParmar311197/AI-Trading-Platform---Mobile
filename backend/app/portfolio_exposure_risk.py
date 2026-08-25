from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExposureLimits:
    max_symbol_quantity: float = 0.0
    max_symbol_notional: float = 0.0
    max_total_notional: float = 0.0
    max_symbol_concentration: float = 1.0


@dataclass(frozen=True)
class ExposureDecision:
    approved: bool
    reason: str
    symbol_quantity: float
    symbol_notional: float
    total_notional: float
    concentration: float


class PortfolioExposureRisk:
    """Fail-closed portfolio exposure gate for proposed orders."""

    def __init__(self, limits: ExposureLimits):
        self.limits = limits

    def evaluate(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        positions: dict[str, float],
        open_order_notional: float = 0.0,
        positions_available: bool = True,
    ) -> ExposureDecision:
        if not positions_available:
            return ExposureDecision(False, "position data unavailable", 0.0, 0.0, 0.0, 1.0)
        if quantity <= 0 or price <= 0:
            return ExposureDecision(False, "invalid order exposure inputs", 0.0, 0.0, 0.0, 1.0)

        key = symbol.strip().upper()
        current_qty = abs(float(positions.get(key, 0.0)))
        proposed_qty = current_qty + quantity
        proposed_notional = proposed_qty * price
        current_total = sum(abs(float(qty)) * price for qty in positions.values())
        total_notional = current_total + quantity * price + max(0.0, open_order_notional)
        concentration = proposed_notional / total_notional if total_notional > 0 else 1.0

        if self.limits.max_symbol_quantity > 0 and proposed_qty > self.limits.max_symbol_quantity:
            return ExposureDecision(False, "max symbol quantity exceeded", proposed_qty, proposed_notional, total_notional, concentration)
        if self.limits.max_symbol_notional > 0 and proposed_notional > self.limits.max_symbol_notional:
            return ExposureDecision(False, "max symbol notional exceeded", proposed_qty, proposed_notional, total_notional, concentration)
        if self.limits.max_total_notional > 0 and total_notional > self.limits.max_total_notional:
            return ExposureDecision(False, "max total portfolio exposure exceeded", proposed_qty, proposed_notional, total_notional, concentration)
        if concentration > self.limits.max_symbol_concentration:
            return ExposureDecision(False, "max symbol concentration exceeded", proposed_qty, proposed_notional, total_notional, concentration)

        return ExposureDecision(True, "within exposure limits", proposed_qty, proposed_notional, total_notional, concentration)
