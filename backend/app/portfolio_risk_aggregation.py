from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PositionRiskInput:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float | None
    multiplier: float = 1.0


@dataclass(frozen=True)
class OpenOrderRiskInput:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float | None
    multiplier: float = 1.0


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    open_position_risk: float
    open_order_risk: float
    total_open_risk: float
    risk_data_available: bool
    unresolved_symbols: tuple[str, ...]


class PortfolioRiskAggregator:
    """Calculate worst-case stop-loss risk from live positions and open orders."""

    @staticmethod
    def _risk(quantity: float, entry: float, stop: float | None, multiplier: float) -> float | None:
        if quantity < 0 or entry <= 0 or multiplier <= 0:
            return None
        if stop is None or stop <= 0:
            return None
        return abs(entry - stop) * quantity * multiplier

    def calculate(
        self,
        positions: Iterable[PositionRiskInput],
        open_orders: Iterable[OpenOrderRiskInput],
    ) -> PortfolioRiskSnapshot:
        position_risk = 0.0
        order_risk = 0.0
        unresolved: set[str] = set()
        for item in positions:
            risk = self._risk(item.quantity, item.entry_price, item.stop_price, item.multiplier)
            if risk is None:
                unresolved.add(item.symbol.upper())
            else:
                position_risk += risk
        for item in open_orders:
            risk = self._risk(item.quantity, item.entry_price, item.stop_price, item.multiplier)
            if risk is None:
                unresolved.add(item.symbol.upper())
            else:
                order_risk += risk
        available = not unresolved
        return PortfolioRiskSnapshot(
            open_position_risk=position_risk,
            open_order_risk=order_risk,
            total_open_risk=position_risk + order_risk,
            risk_data_available=available,
            unresolved_symbols=tuple(sorted(unresolved)),
        )
