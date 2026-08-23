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

    def _recover_broker_order(self, client_order_id: str):
        for order in self.router.get_orders():
            if str(order.get("client_order_id", "")) == client_order_id:
                return order
        return None

    def submit(self, request: BrokerOrderRequest) -> ExecutionResult:
        existing = self.lifecycle.orders.get(request.client_order_id)
        if existing is not None:
            return ExecutionResult(request.client_order_id, existing.status.value, existing.broker_order_id, "IDEMPOTENT_REPLAY")

        recovered = self._recover_broker_order(request.client_order_id)
        if recovered is not None:
            status = str(recovered.get("status", "NEW")).upper()
            lifecycle_status = OrderStatus.FILLED if status in {"FILLED", "TRADED", "COMPLETE"} else OrderStatus.SUBMITTED
            self.lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
            self.lifecycle.orders[request.client_order_id].broker_order_id = str(recovered.get("order_id"))
            self.lifecycle.transition(
                request.client_order_id,
                lifecycle_status,
                filled_quantity=request.quantity if lifecycle_status == OrderStatus.FILLED else 0,
                fill_price=recovered.get("price"),
            )
            self.store.save(self.lifecycle)
            return ExecutionResult(request.client_order_id, lifecycle_status.value, str(recovered.get("order_id")), "BROKER_ORDER_RECOVERED")

        self.lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
        self.store.save(self.lifecycle)
        try:
            result = self.router.submit(request)
            broker_status = str(result.status).upper()
            if broker_status in {"FILLED", "TRADED", "COMPLETE"}:
                self.lifecycle.transition(request.client_order_id, OrderStatus.FILLED, filled_quantity=request.quantity, fill_price=result.price)
            elif broker_status in {"REJECTED", "CANCELLED"}:
                self.lifecycle.transition(request.client_order_id, OrderStatus.REJECTED)
            else:
                self.lifecycle.transition(request.client_order_id, OrderStatus.SUBMITTED)
            self.lifecycle.orders[request.client_order_id].broker_order_id = result.order_id
            self.store.save(self.lifecycle)
            return ExecutionResult(request.client_order_id, self.lifecycle.orders[request.client_order_id].status.value, result.order_id)
        except Exception as exc:
            self.lifecycle.transition(request.client_order_id, OrderStatus.REJECTED)
            self.store.save(self.lifecycle)
            return ExecutionResult(request.client_order_id, OrderStatus.REJECTED.value, message=str(exc))
