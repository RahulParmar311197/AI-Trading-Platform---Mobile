"""Provider-neutral execution boundary.

The port deliberately accepts only a validated OrderIntent plus an explicit
risk authorization. Broker adapters implement the provider-specific side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult


ExecutionStatus = Literal["ACCEPTED", "REJECTED"]


@dataclass(frozen=True)
class ExecutionRequest:
    order: OrderIntent
    authorization: RiskGatewayResult
    idempotency_key: str


@dataclass(frozen=True)
class ExecutionReceipt:
    status: ExecutionStatus
    broker_order_id: str | None = None
    message: str = ""


class ExecutionPort(Protocol):
    """Minimal contract implemented by concrete broker adapters."""

    def submit(self, request: ExecutionRequest) -> ExecutionReceipt:
        ...


def build_execution_request(
    *,
    order: OrderIntent,
    authorization: RiskGatewayResult,
    idempotency_key: str,
) -> ExecutionRequest:
    """Create an execution request only from a successful risk authorization."""
    order.validate()
    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    if not authorization.allowed:
        raise ValueError("execution requires successful risk authorization")
    return ExecutionRequest(
        order=order.normalized(),
        authorization=authorization,
        idempotency_key=idempotency_key.strip(),
    )


__all__ = [
    "ExecutionPort",
    "ExecutionReceipt",
    "ExecutionRequest",
    "build_execution_request",
]
