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

    @staticmethod
    def _validate_recovered_identity(request: BrokerOrderRequest, recovered: dict) -> None:
        recovered_client_id = recovered.get("client_order_id")
        if recovered_client_id is not None and str(recovered_client_id) != str(request.client_order_id):
            raise RuntimeError("broker recovery returned an order for a different client_order_id")
        recovered_symbol = recovered.get("symbol")
        if recovered_symbol is not None and str(recovered_symbol).upper() != str(request.symbol).upper():
            raise RuntimeError("broker recovery returned an order for a different symbol")
        recovered_side = recovered.get("side")
        if recovered_side is not None and str(recovered_side).upper() != str(request.side).upper():
            raise RuntimeError("broker recovery returned an order for a different side")
        recovered_quantity = recovered.get("quantity", recovered.get("requested_quantity"))
        if recovered_quantity is not None:
            try:
                quantity = float(recovered_quantity)
            except (TypeError, ValueError):
                raise RuntimeError("broker recovery returned an invalid requested quantity")
            if abs(quantity - float(request.quantity)) > 1e-9:
                raise RuntimeError("broker recovery returned an order with a different requested quantity")

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
        if requested_quantity <= 0:
            raise ValueError("requested quantity must be positive")
        seen_ids: set[str] = set()
        filled = 0.0
        weighted_value = 0.0
        statuses: list[OrderStatus] = []
        ids: list[str] = []
        for order in orders:
            child_id = order.get("order_id", order.get("broker_order_id"))
            if child_id is None:
                raise RuntimeError("multi-order reconciliation child is missing broker order id")
            child_id = str(child_id)
            if child_id in seen_ids:
                raise RuntimeError(f"duplicate broker child order id: {child_id}")
            seen_ids.add(child_id)
            ids.append(child_id)
            statuses.append(OrderExecutionService._status_value(str(order.get("status", "NEW"))))
            try:
                qty = float(order.get("filled_quantity", order.get("filledQty", 0)) or 0)
            except (TypeError, ValueError):
                raise RuntimeError(f"invalid filled quantity for broker child order: {child_id}")
            if qty < 0:
                raise RuntimeError(f"negative filled quantity for broker child order: {child_id}")
            price = order.get("average_price", order.get("averagePrice", order.get("price")))
            if qty > 0:
                if price is None:
                    raise RuntimeError(f"missing average fill price for broker child order: {child_id}")
                try:
                    price_value = float(price)
                except (TypeError, ValueError):
                    raise RuntimeError(f"invalid average fill price for broker child order: {child_id}")
                if price_value <= 0:
                    raise RuntimeError(f"non-positive average fill price for broker child order: {child_id}")
                weighted_value += price_value * qty
            filled += qty
        if filled > requested_quantity + 1e-9:
            raise RuntimeError("broker reconciliation filled quantity exceeds requested quantity")
        average_price = weighted_value / filled if filled > 0 else None
        if filled >= requested_quantity - 1e-9:
            status = OrderStatus.FILLED.value
        elif filled > 0:
            status = OrderStatus.PARTIALLY_FILLED.value
        elif statuses and all(s == OrderStatus.CANCELLED for s in statuses):
            status = OrderStatus.CANCELLED.value
        elif statuses and all(s == OrderStatus.REJECTED for s in statuses):
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
        self._validate_recovered_identity(request, recovered)
        if recovered.get("multi_order"):
            orders = recovered.get("orders")
            if not isinstance(orders, list) or not orders:
                return ExecutionResult(request.client_order_id, OrderStatus.SUBMITTED.value, message="EXECUTION_PENDING_RECONCILIATION")
            status, filled_quantity, average_price, broker_id = self._aggregate_recovered_orders(orders, request.quantity)
        else:
            broker_id_value = recovered.get("order_id", recovered.get("broker_order_id"))
            if broker_id_value is None:
                raise RuntimeError("broker recovery returned an order without broker order id")
            broker_id = str(broker_id_value)
            status = str(recovered.get("status", "NEW"))
            filled_quantity = float(recovered.get("filled_quantity", recovered.get("filledQty", 0)) or 0)
            average_price = recovered.get("average_price", recovered.get("averagePrice", recovered.get("price")))
            status = self._map_broker_status(status).value
            if filled_quantity < 0:
                raise RuntimeError("broker recovery returned a negative filled quantity")
            if filled_quantity > float(request.quantity) + 1e-9:
                raise RuntimeError("broker recovery returned a filled quantity above requested quantity")
            if filled_quantity > 0 and average_price is None:
                raise RuntimeError("broker recovery returned a fill without an average price")
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
