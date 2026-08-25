from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationState:
    internal_positions: dict[str, float]
    broker_positions: dict[str, float]
    internal_open_order_ids: frozenset[str]
    broker_open_order_ids: frozenset[str]


@dataclass(frozen=True)
class ReconciliationResult:
    clean: bool
    position_differences: tuple[str, ...]
    missing_internal_orders: tuple[str, ...]
    missing_broker_orders: tuple[str, ...]
    reason: str


class TradingStateReconciliationGuard:
    """Compare internal execution state with broker state before new orders."""

    def evaluate(self, state: ReconciliationState) -> ReconciliationResult:
        symbols = set(state.internal_positions) | set(state.broker_positions)
        differences = tuple(sorted(
            symbol for symbol in symbols
            if float(state.internal_positions.get(symbol, 0)) != float(state.broker_positions.get(symbol, 0))
        ))
        missing_internal = tuple(sorted(state.broker_open_order_ids - state.internal_open_order_ids))
        missing_broker = tuple(sorted(state.internal_open_order_ids - state.broker_open_order_ids))
        clean = not differences and not missing_internal and not missing_broker
        if clean:
            reason = "trading state reconciled"
        else:
            reason = "trading state reconciliation drift detected"
        return ReconciliationResult(clean, differences, missing_internal, missing_broker, reason)
