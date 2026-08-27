"""Bridge from the authorized execution port to a broker adapter."""
from __future__ import annotations

from app.brokers.base import BrokerAdapter
from app.execution_port import ExecutionReceipt, ExecutionRequest


def submit_authorized(request: ExecutionRequest, broker: BrokerAdapter) -> ExecutionReceipt:
    """Submit only an already-authorized request through the broker contract."""
    if not request.authorization.allowed:
        raise ValueError("execution requires successful risk authorization")

    order = {
        "symbol": request.order.symbol,
        "side": request.order.side,
        "quantity": request.order.quantity,
        "order_type": request.order.order_type,
        "price": request.order.price,
        "idempotency_key": request.idempotency_key,
    }
    response = broker.place_order(order)
    if not isinstance(response, dict):
        return ExecutionReceipt(status="REJECTED", message="broker returned an invalid response")

    broker_order_id = response.get("order_id") or response.get("broker_order_id")
    status = str(response.get("status", "ACCEPTED")).upper()
    if status in {"REJECTED", "FAILED", "ERROR"}:
        return ExecutionReceipt(status="REJECTED", broker_order_id=broker_order_id, message=str(response.get("message", "broker rejected order")))
    return ExecutionReceipt(status="ACCEPTED", broker_order_id=broker_order_id, message=str(response.get("message", "")))


__all__ = ["submit_authorized"]
