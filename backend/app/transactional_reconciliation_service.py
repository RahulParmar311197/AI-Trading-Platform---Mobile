from __future__ import annotations

from dataclasses import dataclass

from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate, ReconciliationMatcher
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class ReconciliationBinding:
    client_order_id: str
    broker: str
    broker_order_id: str
    method: str


class TransactionalReconciliationService:
    """Single execution-database boundary for reconciliation identity binding."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def bind_deterministic(self, broker: str, snapshot: BrokerOrderSnapshot, candidates: list[InternalOrderCandidate]) -> ReconciliationBinding | None:
        if not broker:
            raise ValueError("broker is required")
        match = ReconciliationMatcher.match(snapshot, candidates)
        if match is None:
            return None
        self.repository.bind_identity(match.client_order_id, broker, match.broker_order_id)
        return ReconciliationBinding(match.client_order_id, broker, match.broker_order_id, match.method)

    def resolve(self, broker: str, broker_order_id: str):
        return self.repository.get_identity_by_broker(broker, broker_order_id)
