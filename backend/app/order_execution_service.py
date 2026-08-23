from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRouter
from app.execution_persistence import ExecutionStateStore
from app.idempotency_store import IdempotencyStore
from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.startup_recovery import StartupRecoveryCoordinator


@dataclass(frozen=True)
class ExecutionResult:
    order_id: str
    status: str
    broker_order_id: str | None = None
    message: str | None = None


class OrderExecutionService:
    _claim_lock = Lock()

    def __init__(self, router: BrokerRouter, lifecycle: OrderLifecycle, store: ExecutionStateStore, idempotency_store: IdempotencyStore | None = None, recovery: StartupRecoveryCoordinator | None = None):
        self.router = router
        self.lifecycle = lifecycle
        self.store = store
        self.idempotency_store = idempotency_store
        self.recovery = recovery or StartupRecoveryCoordinator()

    def _recover_broker_order(self, client_order_id: str):
        return self.router.find_order_by_client_id(client_order_id)

    def _map_broker_status(self, status: str) -> OrderStatus:
        normalized = status.upper().strip()
        if normalized in {"FILLED", "TRADED", "COMPLETE"}:
            return OrderStatus.FILLED
        if normalized in {"PARTIALLY_FILLED", "PART_TRADED", "PARTIALLY_TRADED"}:
            return OrderStatus.PARTIALLY_FILLED
        if normalized in {"CANCELLED", "CANCELED"}:
            return OrderStatus.CANCELLED
        if normalized in {"REJECTED", "FAILED", "ERROR"}:
            return OrderStatus.REJECTED
        return OrderStatus.SUBMITTED

    @staticmethod
    def _aggregate_recovered_orders(orders: list[dict], requested_quantity: float) -> tuple[str, float, float | None, str]:
        filled = 0.0
        weighted_value = 0.0
        statuses: list[str] = []
        ids: list[str] = []
        for order in orders:
            statuses.append(str(order.get("status", "NEW")))
            if order.get("order_id") is not None:
                ids.append(str(order["order_id"]))
            qty = float(order.get("filled_quantity", order.get("filledQty", 0)) or 0)
            price = order.get("average_price", order.get("averagePrice", order.get("price")))
            filled += max(0.0, qty)
            if price is not None and qty > 0:
                weighted_value += float(price) * qty
        if filled > requested_quantity:
            raise RuntimeError("broker reconciliation filled quantity exceeds requested quantity")
        average_price = weighted_value / filled if filled > 0 else None
        mapped = [OrderExecutionService._status_value(s) for s in statuses]
        if filled >= requested_quantity and requested_quantity > 0:
            status = OrderStatus.FILLED.value
        elif filled > 0:
            status = OrderStatus.PARTIALLY_FILLED.value
        elif mapped and all(s == OrderStatus.CANCELLED for s in mapped):
            status = OrderStatus.CANCELLED.value
        elif mapped and all(s == OrderStatus.REJECTED for s in mapped):
            status = OrderStatus.REJECTED.value
        else:
            status = OrderStatus.SUBMITTED.value
        return status, filled, average_price, ",".join(ids)

    @staticmethod
    def _status_value(status: str) -> OrderStatus:
        normalized = status.upper().strip()
        if normalized in {"FILLED", "TRADED", "COMPLETE"}:
            return OrderStatus.FILLED
        if normalized in {"PARTIALLY_FILLED", "PART_TRADED", "PARTIALLY_TRADED"}:
            return OrderStatus.PARTIALLY_FILLED
        if normalized in {"CANCELLED", "CANCELED"}:
            return OrderStatus.CANCELLED
        if normalized in {"REJECTED", "FAILED", "ERROR"}:
            return OrderStatus.REJECTED
        return OrderStatus.SUBMITTED

    def _save_recovered(self, request: BrokerOrderRequest, recovered: dict, message: str) -> ExecutionResult:
        if recovered.get("multi_order"):
            orders = recovered.get("orders")
            if not isinstance(orders, list) or not orders:
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="EXECUTION_PENDING_RECONCILIATION")
            status, filled_quantity, average_price, broker_id = self._aggregate_recovered_orders(orders, request.quantity)
        else:
            broker_id = str(recovered.get("order_id"))
            status = str(recovered.get("status", "NEW"))
            filled_quantity = float(recovered.get("filled_quantity", recovered.get("filledQty", 0)) or 0)
            average_price = recovered.get("average_price", recovered.get("averagePrice", recovered.get("price")))
            status = self._map_broker_status(status).value
        lifecycle_status = OrderStatus(status)
        if request.client_order_id not in self.lifecycle.orders:
            self.lifecycle.create(request.client_order_id, request.symbol, request.side, request.quantity)
        self.lifecycle.orders[request.client_order_id].broker_order_id = broker_id
        fill_qty = filled_quantity if lifecycle_status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED} else 0
        self.lifecycle.transition(request.client_order_id, lifecycle_status, filled_quantity=fill_qty, fill_price=average_price)
        self.store.save(self.lifecycle)
        if self.idempotency_store is not None and lifecycle_status != OrderStatus.PARTIALLY_FILLED:
            self.idempotency_store.mark_completed(request.client_order_id)
        return ExecutionResult(request.client_order_id, lifecycle_status.value, broker_id, message)

    def submit(self, request: BrokerOrderRequest) -> ExecutionResult:
        with self._claim_lock:
            existing = self.lifecycle.orders.get(request.client_order_id)
            if existing is not None and existing.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
                return ExecutionResult(request.client_order_id, existing.status.value, existing.broker_order_id, "IDEMPOTENT_REPLAY")
            if self.recovery.state.value != "READY":
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="LIVE_EXECUTION_LOCKED_STARTUP_RECOVERY_REQUIRED")
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
                lifecycle_status = self._map_broker_status(str(result.status))
                self.lifecycle.transition(request.client_order_id, lifecycle_status, filled_quantity=request.quantity if lifecycle_status == OrderStatus.FILLED else 0, fill_price=result.price)
                self.lifecycle.orders[request.client_order_id].broker_order_id = result.order_id
                self.store.save(self.lifecycle)
                if self.idempotency_store is not None and lifecycle_status != OrderStatus.PARTIALLY_FILLED:
                    self.idempotency_store.mark_completed(request.client_order_id)
                return ExecutionResult(request.client_order_id, lifecycle_status.value, result.order_id)
            except Exception:
                recovered = self._recover_broker_order(request.client_order_id)
                if recovered is not None:
                    return self._save_recovered(request, recovered, "BROKER_ORDER_RECOVERED")
                self.lifecycle.transition(request.client_order_id, OrderStatus.SUBMITTED)
                self.store.save(self.lifecycle)
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="EXECUTION_PENDING_RECONCILIATION")
