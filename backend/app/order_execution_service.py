from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_lifecycle import OrderLifecycle, OrderStatus


@dataclass(frozen=True)
class ExecutionResult:
    order_id: str
    status: str
    broker_order_id: str | None = None
    message: str | None = None


class OrderExecutionService:
    _claim_lock = Lock()

    def __init__(self, router: BrokerRouter, lifecycle: OrderLifecycle, store: ExecutionStateStore, idempotency_store: IdempotencyStore | None = None):
        self.router = router
        self.lifecycle = lifecycle
        self.store = store
        self.idempotency_store = idempotency_store

    def _recover_broker_order(self, client_order_id: str):
        return self.router.find_order_by_client_id(client_order_id)

    def _save_recovered(self, request: BrokerOrderRequest, recovered: dict, message: str) -> ExecutionResult:
        broker_id = str(recovered.get("order_id"))
        status = str(recovered.get("status", "NEW")).upper()
        lifecycle_status = OrderStatus.FILLED if status in {"FILLED", "TRADED", "COMPLETE"} else OrderStatus.SUBMITTED
        if request.client_order_id not in self.lifecycle.orders:
            self.lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
        self.lifecycle.orders[request.client_order_id].broker_order_id = broker_id
        self.lifecycle.transition(request.client_order_id, lifecycle_status, filled_quantity=request.quantity if lifecycle_status == OrderStatus.FILLED else 0, fill_price=recovered.get("price"))
        self.store.save(self.lifecycle)
        if self.idempotency_store is not None:
            self.idempotency_store.mark_completed(request.client_order_id)
        return ExecutionResult(request.client_order_id, lifecycle_status.value, broker_id, message)

    def submit(self, request: BrokerOrderRequest) -> ExecutionResult:
        with self._claim_lock:
            existing = self.lifecycle.orders.get(request.client_order_id)
            if existing is not None and existing.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                return ExecutionResult(request.client_order_id, existing.status.value, existing.broker_order_id, "IDEMPOTENT_REPLAY")

            if self.idempotency_store is not None and not self.idempotency_store.claim(request.client_order_id):
                recovered = self._recover_broker_order(request.client_order_id)
                if recovered is not None:
                    return self._save_recovered(request, recovered, "BROKER_ORDER_RECOVERED")
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="EXECUTION_PENDING_RECONCILIATION")

            recovered = self._recover_broker_order(request.client_order_id)
            if recovered is not None:
                return self._save_recovered(request, recovered, "BROKER_ORDER_RECOVERED")

            if request.client_order_id not in self.lifecycle.orders:
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
                if self.idempotency_store is not None:
                    self.idempotency_store.mark_completed(request.client_order_id)
                return ExecutionResult(request.client_order_id, self.lifecycle.orders[request.client_order_id].status.value, result.order_id)
            except Exception:
                recovered = self._recover_broker_order(request.client_order_id)
                if recovered is not None:
                    return self._save_recovered(request, recovered, "BROKER_ORDER_RECOVERED")
                self.lifecycle.transition(request.client_order_id, OrderStatus.SUBMITTED)
                self.store.save(self.lifecycle)
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="EXECUTION_PENDING_RECONCILIATION")
