from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from app.execution_observability import ExecutionObservability
from app.execution_safety_gate import ExecutionSafetyContext, ExecutionSafetyGate
from app.transactional_execution_repository import TransactionalExecutionRepository


class AmbiguousBrokerSubmission(RuntimeError):
    """Broker outcome is unknown; reconcile the durable pending submission before retry."""


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


class BrokerOrderLookup(Protocol):
    def lookup(self, client_order_id: str, broker_account_id: int, broker_route: str) -> list[BrokerSubmissionResult]: ...


class OrderSubmissionService:
    """Single outbound order boundary backed by durable state and execution metrics."""

    def __init__(self, repository: TransactionalExecutionRepository, adapter: BrokerOrderAdapter, safety_gate: ExecutionSafetyGate | None = None, observability: ExecutionObservability | None = None, lookup: BrokerOrderLookup | None = None) -> None:
        self.repository = repository
        self.adapter = adapter
        self.safety_gate = safety_gate or ExecutionSafetyGate()
        self.observability = observability or ExecutionObservability()
        self.lookup = lookup

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
        started = monotonic()
        try:
            result = self.adapter.submit(intent)
        except Exception as exc:
            self.observability.observe_latency("broker_latency", (monotonic() - started) * 1000)
            self.observability.increment("broker_failures")
            self.observability.increment("ambiguous_submissions")
            raise AmbiguousBrokerSubmission("broker submission outcome is unknown; reconcile the pending submission before retry") from exc
        self.observability.observe_latency("broker_latency", (monotonic() - started) * 1000)
        if not result.broker_order_id or result.client_order_id != intent.client_order_id:
            self.observability.increment("ambiguous_submissions")
            raise AmbiguousBrokerSubmission("broker submission response is invalid or cannot be safely identified; reconcile before retry")
        self.repository.mark_submission_submitted(intent.idempotency_key, result.broker_order_id)
        self.observability.increment("submitted")
        return result

    def reconcile_pending(self, *, limit: int = 100) -> list[BrokerSubmissionResult]:
        pending = self.repository.pending_submissions(limit)
        if not pending:
            return []
        if self.lookup is None:
            raise AmbiguousBrokerSubmission("broker lookup is required to reconcile pending submissions")
        resolved: list[BrokerSubmissionResult] = []
        for record in pending:
            try:
                matches = self.lookup.lookup(record.client_order_id, record.broker_account_id, record.broker_route)
            except Exception as exc:
                self.observability.increment("broker_failures")
                raise AmbiguousBrokerSubmission(f"broker lookup unavailable for pending submission {record.idempotency_key}") from exc
            if len(matches) == 0:
                continue
            if len(matches) != 1:
                raise AmbiguousBrokerSubmission(f"multiple broker orders match pending submission {record.idempotency_key}")
            match = matches[0]
            if not match.broker_order_id or match.client_order_id != record.client_order_id:
                raise AmbiguousBrokerSubmission(f"broker identity mismatch for pending submission {record.idempotency_key}")
            reconciled = self.repository.mark_submission_submitted(record.idempotency_key, match.broker_order_id)
            resolved.append(BrokerSubmissionResult(reconciled.broker_order_id or match.broker_order_id, reconciled.client_order_id))
            self.observability.increment("reconciled_submissions")
        return resolved

    def recover_pending(self, *, limit: int = 100) -> list[BrokerSubmissionResult]:
        pending = self.repository.pending_submissions(limit)
        if pending:
            raise AmbiguousBrokerSubmission(f"manual broker reconciliation required for pending submission {pending[0].idempotency_key}")
        return []
