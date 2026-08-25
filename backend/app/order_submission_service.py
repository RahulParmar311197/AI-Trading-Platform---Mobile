from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.execution_observability import ExecutionObservability
from app.execution_safety_gate import ExecutionSafetyContext, ExecutionSafetyGate
from app.transactional_execution_repository import TransactionalExecutionRepository


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
    """Single outbound order boundary backed by durable state and execution metrics."""

    def __init__(self, repository: TransactionalExecutionRepository, adapter: BrokerOrderAdapter, safety_gate: ExecutionSafetyGate | None = None, observability: ExecutionObservability | None = None) -> None:
        self.repository = repository
        self.adapter = adapter
        self.safety_gate = safety_gate or ExecutionSafetyGate()
        self.observability = observability or ExecutionObservability()

    def submit(self, intent: OrderIntent, *, reconciliation_ready: bool = True, broker_healthy: bool = True, risk_allowed: bool = True, emergency_halt: bool = False) -> BrokerSubmissionResult:
        self.observability.increment("submissions")
        if not intent.idempotency_key:
            raise ValueError("idempotency key is required")
        if intent.quantity <= 0 or not intent.symbol or intent.side not in {"BUY", "SELL"}:
            raise ValueError("invalid order intent")
        authorization = self.safety_gate.authorize(ExecutionSafetyContext(emergency_halt, reconciliation_ready, broker_healthy, risk_allowed, intent.broker_account_id, intent.broker_route))
        if not authorization.allowed:
            raise PermissionError(f"order submission blocked: {authorization.reason.value}")
        order = self.repository.get_order(intent.client_order_id)
        if order is None:
            raise KeyError(intent.client_order_id)
        if (order["symbol"], order["side"], float(order["quantity"]), order["broker_account_id"], order["broker_route"]) != (intent.symbol.upper(), intent.side.upper(), float(intent.quantity), intent.broker_account_id, intent.broker_route):
            raise ValueError("order intent does not match durable order scope")
        record = self.repository.register_submission(intent.idempotency_key, intent.client_order_id, intent.broker_account_id, intent.broker_route)
        if record.status == "SUBMITTED" and record.broker_order_id:
            self.observability.increment("duplicate_preventions")
            return BrokerSubmissionResult(record.broker_order_id, record.client_order_id)
        try:
            result = self.adapter.submit(intent)
        except Exception:
            self.observability.increment("broker_failures")
            raise
        self.repository.mark_submission_submitted(intent.idempotency_key, result.broker_order_id)
        self.observability.increment("submitted")
        return result

    def recover_pending(self, *, limit: int = 100) -> list[BrokerSubmissionResult]:
        results: list[BrokerSubmissionResult] = []
        for record in self.repository.pending_submissions(limit):
            raise RuntimeError(f"manual broker reconciliation required for pending submission {record.idempotency_key}")
        return results
