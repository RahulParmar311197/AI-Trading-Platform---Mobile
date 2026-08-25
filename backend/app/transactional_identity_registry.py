from __future__ import annotations

from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


class TransactionalIdentityRegistry:
    """Compatibility facade backed exclusively by the execution repository transaction boundary."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def bind(self, identity: OrderIdentity) -> None:
        self.repository.bind_identity(identity)

    def by_broker(self, broker: str, broker_order_id: str) -> OrderIdentity | None:
        return self.repository.get_identity_by_broker(broker, broker_order_id)

    def bind_and_apply_event(self, identity: OrderIdentity, event_id: str, kind: str, *, broker_account_id: int, broker_route: str, price: float | None = None, quantity: float = 0.0) -> bool:
        return self.repository.bind_identity_and_apply_event(identity, event_id, kind, broker_account_id=broker_account_id, broker_route=broker_route, price=price, quantity=quantity)
