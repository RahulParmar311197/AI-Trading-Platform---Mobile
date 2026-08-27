from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.broker_reconciliation import BrokerOrderSnapshot, LocalOrderSnapshot, OrderReconciler, ReconciliationIssue
from app.safety_state import SafetyStateStore


@dataclass(frozen=True)
class PostTradeReconciliationResult:
    issues: tuple[ReconciliationIssue, ...]
    matched: bool


class PostTradeReconciler:
    """Reconcile local order state with broker truth after execution."""

    def __init__(self, order_reconciler: OrderReconciler | None = None, safety_store: SafetyStateStore | None = None) -> None:
        self.order_reconciler = order_reconciler or OrderReconciler()
        self.safety_store = safety_store

    def _finalize(self, issues: tuple[ReconciliationIssue, ...]) -> PostTradeReconciliationResult:
        if issues and self.safety_store is not None:
            self.safety_store.halt("post-trade broker reconciliation drift detected")
        return PostTradeReconciliationResult(issues, not issues)

    def reconcile_orders(self, local_orders: Mapping[str, LocalOrderSnapshot], broker_orders: list[BrokerOrderSnapshot]) -> PostTradeReconciliationResult:
        issues = tuple(self.order_reconciler.reconcile(local_orders, broker_orders))
        return self._finalize(issues)

    def reconcile_execution_result(self, local_order: LocalOrderSnapshot, broker_order: BrokerOrderSnapshot) -> PostTradeReconciliationResult:
        issues = tuple(self.order_reconciler.reconcile({local_order.broker_order_id: local_order}, [broker_order]))
        return self._finalize(issues)
