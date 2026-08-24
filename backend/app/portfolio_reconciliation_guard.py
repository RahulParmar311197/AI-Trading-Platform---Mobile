from __future__ import annotations

from app.portfolio_reconciliation_service import PortfolioReconciliationService, ReconciliationResult
from app.safety_state import SafetyState, SafetyStateStore


class PortfolioReconciliationGuard:
    """Turns broker/local exposure mismatches into a persistent trading halt."""

    def __init__(self, safety_store: SafetyStateStore, reconciliation: PortfolioReconciliationService | None = None):
        self.safety_store = safety_store
        self.reconciliation = reconciliation or PortfolioReconciliationService()

    def reconcile(self, local_positions: dict[str, float], broker_positions: list[dict]) -> ReconciliationResult:
        result = self.reconciliation.compare(local_positions, broker_positions)
        if result.matched:
            state = self.safety_store.load()
            if state.trading_halted and state.halt_reason and state.halt_reason.startswith("PORTFOLIO_MISMATCH"):
                self.safety_store.clear()
        else:
            details = "; ".join(f"{m.symbol}: local={m.local_quantity}, broker={m.broker_quantity}" for m in result.mismatches)
            self.safety_store.halt(f"PORTFOLIO_MISMATCH: {details}")
        return result

    def assert_trading_allowed(self) -> SafetyState:
        state = self.safety_store.load()
        if state.trading_halted:
            raise RuntimeError(f"TRADING_HALTED: {state.halt_reason or 'safety state active'}")
        return state
