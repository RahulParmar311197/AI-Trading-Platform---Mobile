from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.order_lifecycle import OrderLifecycle
from app.order_reconciliation import BrokerOrder, OrderReconciler, ReconciliationEvent


@dataclass(frozen=True)
class OrderReconciliationResult:
    events: tuple[ReconciliationEvent, ...]

    @property
    def alerts(self) -> tuple[ReconciliationEvent, ...]:
        return tuple(e for e in self.events if e.action.value == "ALERT")

    @property
    def changed(self) -> bool:
        return any(e.action.value in {"CREATE", "UPDATE"} for e in self.events)


class OrderReconciliationService:
    """Application service facade over the existing order reconciliation engine."""

    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle
        self.reconciler = OrderReconciler(lifecycle)

    def reconcile(self, broker_orders: Iterable[BrokerOrder]) -> OrderReconciliationResult:
        return OrderReconciliationResult(events=tuple(self.reconciler.reconcile(list(broker_orders))))

    def reconcile_pending(self, broker_orders: Iterable[BrokerOrder]) -> OrderReconciliationResult:
        return OrderReconciliationResult(events=tuple(self.reconciler.reconcile_pending(list(broker_orders))))

    def reconcile_or_raise(self, broker_orders: Iterable[BrokerOrder]) -> OrderReconciliationResult:
        result = self.reconcile(broker_orders)
        if result.alerts:
            reasons = "; ".join(event.reason for event in result.alerts)
            raise RuntimeError(f"order reconciliation produced alerts: {reasons}")
        return result
