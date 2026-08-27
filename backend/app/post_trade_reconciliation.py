from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.broker_reconciliation import BrokerOrderSnapshot, LocalOrderSnapshot, OrderReconciler, ReconciliationIssue


@dataclass(frozen=True)
class PostTradeReconciliationResult:
    issues: tuple[ReconciliationIssue, ...]
    matched: bool


class PostTradeReconciler:
    """Reconcile local order state with broker truth after execution."""

    def __init__(self, order_reconciler: OrderReconciler | None = None) -> None:
        self.order_reconciler = order_reconciler or OrderReconciler()

    def reconcile_orders(self, local_orders: Mapping[str, LocalOrderSnapshot], broker_orders: list[BrokerOrderSnapshot]) -> PostTradeReconciliationResult:
        issues = tuple(self.order_reconciler.reconcile(local_orders, broker_orders))
        return PostTradeReconciliationResult(issues, not issues)

    def reconcile_execution_result(self, local_order: LocalOrderSnapshot, broker_order: BrokerOrderSnapshot) -> PostTradeReconciliationResult:
        issues = tuple(self.order_reconciler.reconcile({local_order.broker_order_id: local_order}, [broker_order]))
        return PostTradeReconciliationResult(issues, not issues)
