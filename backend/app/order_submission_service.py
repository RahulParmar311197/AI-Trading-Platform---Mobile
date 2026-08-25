from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.execution_safety_gate import ExecutionSafetyContext, ExecutionSafetyGate


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    broker_account_id: int
    broker_route: str
    idempotency_key: str


@dataclass(frozen=True)
class BrokerSubmissionResult:
    broker_order_id: str
    client_order_id: str


class BrokerOrderAdapter(Protocol):
    def submit(self, intent: OrderIntent) -> BrokerSubmissionResult: ...


class OrderSubmissionService:
    """Single outbound order boundary: safety checks precede broker submission."""

    def __init__(self, adapter: BrokerOrderAdapter, safety_gate: ExecutionSafetyGate | None = None) -> None:
        self.adapter = adapter
        self.safety_gate = safety_gate or ExecutionSafetyGate()
        self._submitted: dict[str, BrokerSubmissionResult] = {}

    def submit(self, intent: OrderIntent, *, reconciliation_ready: bool = True, broker_healthy: bool = True, risk_allowed: bool = True, emergency_halt: bool = False) -> BrokerSubmissionResult:
        if not intent.idempotency_key:
            raise ValueError("idempotency key is required")
        if intent.quantity <= 0 or not intent.symbol or intent.side not in {"BUY", "SELL"}:
            raise ValueError("invalid order intent")
        authorization = self.safety_gate.authorize(ExecutionSafetyContext(emergency_halt, reconciliation_ready, broker_healthy, risk_allowed, intent.broker_account_id, intent.broker_route))
        if not authorization.allowed:
            raise PermissionError(f"order submission blocked: {authorization.reason.value}")
        existing = self._submitted.get(intent.idempotency_key)
        if existing is not None:
            return existing
        result = self.adapter.submit(intent)
        self._submitted[intent.idempotency_key] = result
        return result
