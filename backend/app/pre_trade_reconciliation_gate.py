from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker_reconciliation import ReconciliationReport, reconcile_positions


class PreTradeReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreTradeReconciliationPolicy:
    enabled: bool = True
    quantity_tolerance: float = 0.0
    block_on_mismatch: bool = True


class PreTradeReconciliationGate:
    """Fail closed when local and broker positions disagree before live execution."""

    def __init__(self, policy: PreTradeReconciliationPolicy | None = None) -> None:
        self.policy = policy or PreTradeReconciliationPolicy()

    def check(self, local_positions: list[dict[str, Any]], broker_positions: list[dict[str, Any]]) -> ReconciliationReport:
        if not self.policy.enabled:
            return ReconciliationReport(True, (), (), ())
        report = reconcile_positions(local_positions, broker_positions, quantity_tolerance=self.policy.quantity_tolerance)
        if self.policy.block_on_mismatch and not report.matched:
            raise PreTradeReconciliationError(f"trading blocked: broker/local position mismatch ({len(report.deltas)} symbol deltas)")
        return report
