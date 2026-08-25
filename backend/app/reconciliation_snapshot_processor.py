from __future__ import annotations

from dataclasses import dataclass

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry
from app.reconciliation_event_recovery import IdentityMatch, ReconciliationEventRecovery
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate, ReconciliationMatcher


@dataclass(frozen=True)
class SnapshotProcessResult:
    matched: int
    unmatched: int
    ambiguous: int
    recovered: int


class ReconciliationSnapshotProcessor:
    """Apply only deterministic reconciliation matches; quarantine ambiguity."""

    def __init__(self, registry: OrderIdentityRegistry, quarantine: ExecutionEventQuarantine, recovery: ReconciliationEventRecovery) -> None:
        self.registry = registry
        self.quarantine = quarantine
        self.recovery = recovery

    def process(self, broker_orders: list[BrokerOrderSnapshot], candidates: list[InternalOrderCandidate]) -> SnapshotProcessResult:
        matched = ambiguous = unmatched = 0
        for broker in broker_orders:
            result = ReconciliationMatcher.match(broker, candidates)
            if result is None:
                same_attrs = [c for c in candidates if c.symbol.upper() == broker.symbol.upper() and c.side.upper() == broker.side.upper() and c.quantity == broker.quantity]
                if len(same_attrs) > 1:
                    ambiguous += 1
                    reason = "AMBIGUOUS_RECONCILIATION_MATCH"
                else:
                    unmatched += 1
                    reason = "NO_DETERMINISTIC_RECONCILIATION_MATCH"
                self.quarantine.quarantine(event_id=f"reconcile:{broker.broker_order_id}", broker="reconciliation", broker_order_id=broker.broker_order_id, payload={"symbol":broker.symbol,"side":broker.side,"quantity":broker.quantity,"timestamp":broker.timestamp.isoformat()}, reason=reason)
                continue
            self.registry.bind(OrderIdentity(result.client_order_id, "reconciliation", result.broker_order_id))
            matched += 1
        recovery = self.recovery.recover()
        return SnapshotProcessResult(matched, unmatched, ambiguous, recovery.recovered)
