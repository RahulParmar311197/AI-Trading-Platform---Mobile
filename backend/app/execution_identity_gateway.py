from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_event import CanonicalExecutionEvent
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class ResolvedExecutionIdentity:
    client_order_id: str
    broker: str
    broker_order_id: str


class ExecutionIdentityGateway:
    """Single identity lookup/write gateway backed by the execution repository."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def resolve(self, event: CanonicalExecutionEvent) -> ResolvedExecutionIdentity | None:
        identity = self.repository.get_identity_by_broker(event.broker, event.broker_order_id)
        if identity is None:
            return None
        return ResolvedExecutionIdentity(identity.client_order_id, identity.broker, identity.broker_order_id)

    def bind(self, client_order_id: str, broker: str, broker_order_id: str) -> None:
        self.repository.bind_identity(client_order_id, broker, broker_order_id)
