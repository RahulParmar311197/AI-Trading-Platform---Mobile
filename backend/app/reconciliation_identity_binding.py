from __future__ import annotations

from dataclasses import dataclass

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry
from app.reconciliation_event_recovery import ReconciliationEventRecovery
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate, ReconciliationMatcher


@dataclass(frozen=True)
class BindingResult:
    bound: bool
    reason: str
    client_order_id: str | None = None


class ReconciliationIdentityBinder:
    """Persist only deterministic reconciliation matches using the real broker namespace."""

    def __init__(self, registry: OrderIdentityRegistry) -> None:
        self.registry = registry

    def bind(self, broker_name: str, snapshot: BrokerOrderSnapshot, candidates: list[InternalOrderCandidate]) -> BindingResult:
        if not broker_name:
            raise ValueError("broker_name is required")
        match = ReconciliationMatcher.match(snapshot, candidates)
        if match is None:
            return BindingResult(False, "NO_DETERMINISTIC_MATCH")
        existing = self.registry.by_broker(broker_name, snapshot.broker_order_id)
        if existing is not None and existing.client_order_id != match.client_order_id:
            return BindingResult(False, "BROKER_ORDER_ALREADY_BOUND")
        self.registry.bind(OrderIdentity(match.client_order_id, broker_name, snapshot.broker_order_id))
        return BindingResult(True, match.method, match.client_order_id)
