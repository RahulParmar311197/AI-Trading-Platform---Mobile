from __future__ import annotations

from dataclasses import dataclass

from app.execution_lifecycle import OrderStatus
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class LiveExecutionOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float


class LiveExecutionRepositoryBridge:
    """Small integration boundary for broker adapters to use the transactional repository."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def create_order(self, *, symbol: str, side: str, quantity: float) -> LiveExecutionOrder:
        order_id = self.repository.create_order(symbol, side, quantity)
        return LiveExecutionOrder(order_id, symbol.upper(), side.upper(), quantity)

    def submitted(self, *, event_id: str, order_id: str) -> bool:
        return self.repository.apply_event(event_id, order_id, "SUBMITTED")

    def fill(self, *, event_id: str, order_id: str, quantity: float, price: float | None = None) -> bool:
        return self.repository.apply_event(event_id, order_id, "FILL", quantity=quantity, price=price)

    def cancelled(self, *, event_id: str, order_id: str) -> bool:
        return self.repository.apply_event(event_id, order_id, OrderStatus.CANCELLED.value)

    def rejected(self, *, event_id: str, order_id: str) -> bool:
        return self.repository.apply_event(event_id, order_id, OrderStatus.REJECTED.value)

    def state(self):
        return self.repository.snapshot()
