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
    broker_account_id: int
    broker_route: str


class LiveExecutionRepositoryBridge:
    """Execution integration boundary with mandatory broker-account identity and ordering."""

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        broker_account_id: int,
        broker_route: str,
    ) -> LiveExecutionOrder:
        order_id = self.repository.create_order(
            symbol,
            side,
            quantity,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
        )
        return LiveExecutionOrder(
            order_id,
            symbol.upper(),
            side.upper(),
            quantity,
            broker_account_id,
            broker_route,
        )

    def _require_transition(
        self,
        order_id: str,
        *,
        broker_account_id: int,
        broker_route: str,
        allowed: set[str],
    ) -> None:
        order = self.repository.get_order(order_id)
        if order is None:
            raise KeyError(order_id)
        if order["broker_account_id"] != broker_account_id or order["broker_route"] != broker_route:
            raise ValueError("broker account identity mismatch")
        if order["status"] not in allowed:
            raise ValueError(f"invalid live execution transition from {order['status']}")

    def submitted(
        self,
        *,
        event_id: str,
        order_id: str,
        broker_account_id: int,
        broker_route: str,
        event_sequence: int,
    ) -> bool:
        self._require_transition(
            order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            allowed={OrderStatus.CREATED.value, OrderStatus.RISK_APPROVED.value},
        )
        return self.repository.apply_broker_event(
            event_id,
            order_id,
            "SUBMITTED",
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            event_sequence=event_sequence,
        )

    def fill(
        self,
        *,
        event_id: str,
        order_id: str,
        quantity: float,
        broker_account_id: int,
        broker_route: str,
        event_sequence: int,
        price: float | None = None,
    ) -> bool:
        self._require_transition(
            order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            allowed={OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value},
        )
        return self.repository.apply_broker_event(
            event_id,
            order_id,
            "FILL",
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            quantity=quantity,
            price=price,
            event_sequence=event_sequence,
        )

    def cancelled(
        self,
        *,
        event_id: str,
        order_id: str,
        broker_account_id: int,
        broker_route: str,
        event_sequence: int,
    ) -> bool:
        self._require_transition(
            order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            allowed={OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value},
        )
        return self.repository.apply_broker_event(
            event_id,
            order_id,
            OrderStatus.CANCELLED.value,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            event_sequence=event_sequence,
        )

    def rejected(
        self,
        *,
        event_id: str,
        order_id: str,
        broker_account_id: int,
        broker_route: str,
        event_sequence: int,
    ) -> bool:
        self._require_transition(
            order_id,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            allowed={OrderStatus.CREATED.value, OrderStatus.SUBMITTED.value},
        )
        return self.repository.apply_broker_event(
            event_id,
            order_id,
            OrderStatus.REJECTED.value,
            broker_account_id=broker_account_id,
            broker_route=broker_route,
            event_sequence=event_sequence,
        )

    def state(self):
        return self.repository.snapshot()
