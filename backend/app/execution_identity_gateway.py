from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_event import CanonicalExecutionEvent
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


@dataclass(frozen=True)
class ResolvedExecutionIdentity:
    client_order_id: str
    broker: str
    broker_order_id: str
    broker_account_id: int
    broker_route: str


class ExecutionIdentityGateway:
    """Single identity lookup/write gateway with mandatory broker-account scope."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def _scope(self, event: CanonicalExecutionEvent) -> tuple[int, str]:
        if event.broker_account_id is None or not event.broker_route:
            raise ValueError("broker account identity is required")
        return event.broker_account_id, event.broker_route

    def resolve(self, event: CanonicalExecutionEvent) -> ResolvedExecutionIdentity | None:
        account_id, route = self._scope(event)
        identity = self.repository.get_identity_by_broker(event.broker, event.broker_order_id, broker_account_id=account_id, broker_route=route)
        if identity is None:
            return None
        return ResolvedExecutionIdentity(identity.client_order_id, identity.broker, identity.broker_order_id, account_id, route)

    def bind(self, client_order_id: str, broker: str, broker_order_id: str, *, broker_account_id: int, broker_route: str) -> None:
        self.repository.bind_identity(OrderIdentity(client_order_id, broker, broker_order_id, broker_account_id, broker_route))
