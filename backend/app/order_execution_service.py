from __future__ import annotations

from dataclasses import dataclass

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle, OrderStatus


@dataclass(frozen=True)
class ExecutionResult:
    order_id: str
    status: str
    broker_order_id: str | None = None
    message: str | None = None


class OrderExecutionService:
    """Single orchestration boundary between API orders and broker execution."""

    def __init__(self, router: BrokerRouter, lifecycle: OrderLifecycle, store: ExecutionStateStore):
        self.router = router
        self.lifecycle = lifecycle
        self.store = store

    def submit(self, request: BrokerOrderRequest) -> ExecutionResult:
        existing = self.lifecycle.orders.get(request.client_order_id)
        if existing is not None:
            return ExecutionResult(
                request.client_order_id,
                existing.status.value,
                existing.broker_order_id,
                "IDEMPOTENT_REPLAY",
            )

        self.lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
        self.store.save(self.lifecycle)
        try:
            result = self.router.submit(request)
            broker_status = str(result.status).upper()
            if broker_status in {"FILLED", "TRADED", "COMPLETE"}:
                self.lifecycle.transition(
                    request.client_order_id,
                    OrderStatus.FILLED,
                    filled_quantity=request.quantity,
                    fill_price=result.price,
                )
            elif broker_status in {"REJECTED", "CANCELLED"}:
                self.lifecycle.transition(request.client_order_id, OrderStatus.REJECTED)
            else:
                self.lifecycle.transition(request.client_order_id, OrderStatus.SUBMITTED)
            self.lifecycle.orders[request.client_order_id].broker_order_id = result.order_id
            self.store.save(self.lifecycle)
            return ExecutionResult(
                request.client_order_id,
                self.lifecycle.orders[request.client_order_id].status.value,
                result.order_id,
            )
        except Exception as exc:
            self.lifecycle.transition(request.client_order_id, OrderStatus.REJECTED)
            self.store.save(self.lifecycle)
            return ExecutionResult(request.client_order_id, OrderStatus.REJECTED.value, message=str(exc))
