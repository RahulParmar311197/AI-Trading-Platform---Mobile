from __future__ import annotations

from dataclasses import dataclass
from app.portfolio_reconciliation_service import PortfolioReconciliationService, ReconciliationResult
from app.safety_state import SafetyStateStore
from app.startup_recovery import RecoveryState, StartupRecoveryCoordinator

@dataclass(frozen=True)
class StartupGateResult:
    ready: bool
    reason: str | None = None
    reconciliation: ReconciliationResult | None = None

class StartupReconciliationGate:
    """Keep live execution locked until startup order and portfolio state are safe."""

    def __init__(self, recovery: StartupRecoveryCoordinator, safety_store: SafetyStateStore, reconciliation: PortfolioReconciliationService | None = None):
        self.recovery = recovery; self.safety_store = safety_store; self.reconciliation = reconciliation or PortfolioReconciliationService()

    def evaluate(self, local_positions: dict[str, float], broker_positions: list[dict]) -> StartupGateResult:
        if self.recovery.state != RecoveryState.READY:
            return StartupGateResult(False, f"STARTUP_RECOVERY_NOT_READY:{self.recovery.state.value}")
        result = self.reconciliation.compare(local_positions, broker_positions)
        if result.errors:
            self.safety_store.halt("PORTFOLIO_RECONCILIATION_INVALID:" + "; ".join(result.errors))
            return StartupGateResult(False, "PORTFOLIO_RECONCILIATION_INVALID", result)
        if not result.matched:
            details = "; ".join(f"{m.symbol}: local={m.local_quantity}, broker={m.broker_quantity}" for m in result.mismatches)
            self.safety_store.halt(f"PORTFOLIO_MISMATCH:{details}")
            return StartupGateResult(False, "PORTFOLIO_MISMATCH", result)
        state = self.safety_store.load()
        if state.trading_halted:
            return StartupGateResult(False, f"SAFETY_HALT_ACTIVE:{state.halt_reason or 'unknown'}", result)
        return StartupGateResult(True, None, result)

    def require_ready(self, local_positions: dict[str, float], broker_positions: list[dict]) -> StartupGateResult:
        result = self.evaluate(local_positions, broker_positions)
        if not result.ready:
            raise RuntimeError(result.reason or "startup execution gate blocked")
        return result
