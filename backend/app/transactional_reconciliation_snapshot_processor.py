from __future__ import annotations

from dataclasses import dataclass

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate
from app.transactional_execution_repository import TransactionalExecutionRepository
from app.transactional_reconciliation_service import TransactionalReconciliationService


@dataclass(frozen=True)
class TransactionalSnapshotResult:
    matched: int
    unmatched: int
    ambiguous: int


class TransactionalReconciliationSnapshotProcessor:
    """Process snapshots without consulting the legacy identity registry."""

    def __init__(self, repository: TransactionalExecutionRepository, quarantine: ExecutionEventQuarantine) -> None:
        self.repository = repository
        self.quarantine = quarantine
        self.reconciliation = TransactionalReconciliationService(repository)

    def process(self, broker: str, broker_orders: list[BrokerOrderSnapshot], candidates: list[InternalOrderCandidate]) -> TransactionalSnapshotResult:
        matched = unmatched = ambiguous = 0
        for snapshot in broker_orders:
            binding = self.reconciliation.bind_deterministic(broker, snapshot, candidates)
            if binding is not None:
                matched += 1
                continue
            same_attrs = [c for c in candidates if c.symbol.upper() == snapshot.symbol.upper() and c.side.upper() == snapshot.side.upper() and c.quantity == snapshot.quantity]
            ambiguous += len(same_attrs) > 1
            unmatched += len(same_attrs) <= 1
            reason = "AMBIGUOUS_RECONCILIATION_MATCH" if len(same_attrs) > 1 else "NO_DETERMINISTIC_RECONCILIATION_MATCH"
            self.quarantine.quarantine(
                event_id=f"reconcile:{broker}:{snapshot.broker_order_id}",
                broker=broker,
                broker_order_id=snapshot.broker_order_id,
                payload={"symbol": snapshot.symbol, "side": snapshot.side, "quantity": snapshot.quantity, "timestamp": snapshot.timestamp.isoformat()},
                reason=reason,
            )
        return TransactionalSnapshotResult(matched, unmatched, ambiguous)
