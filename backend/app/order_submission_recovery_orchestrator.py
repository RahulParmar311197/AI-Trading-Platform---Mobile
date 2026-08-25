from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.broker_submission_recovery import SubmissionRecoveryService
from app.execution_observability import ExecutionObservability
from app.order_submission_service import BrokerSubmissionResult, OrderIntent
from app.submission_recovery_audit import SubmissionRecoveryAuditor
from app.submission_recovery_authorization import RecoveryApproval, RecoveryAuthorizer
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class RecoveryResult:
    idempotency_key: str
    status: str
    broker_order_id: str | None = None
    reason: str | None = None


class OrderSubmissionRecoveryOrchestrator:
    """Canonical restart path for durable PENDING outbound orders with audit, authorization and metrics."""

    def __init__(self, repository: TransactionalExecutionRepository, recovery: SubmissionRecoveryService, auditor: SubmissionRecoveryAuditor | None = None, authorizer: RecoveryAuthorizer | None = None, observability: ExecutionObservability | None = None) -> None:
        self.repository = repository
        self.recovery = recovery
        self.auditor = auditor or SubmissionRecoveryAuditor()
        if authorizer is None:
            raise ValueError("recovery authorizer is required")
        self.authorizer = authorizer
        self.observability = observability or ExecutionObservability()

    def recover_pending(self, *, limit: int = 100, approval: RecoveryApproval) -> list[RecoveryResult]:
        results: list[RecoveryResult] = []
        for record in self.repository.pending_submissions(limit=limit):
            if approval.broker_account_id != record.broker_account_id or approval.broker_route != record.broker_route:
                reason = "recovery approval is outside broker account scope"
                self.observability.increment("quarantined")
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            try:
                self.authorizer.authorize(approval)
            except PermissionError as exc:
                reason = str(exc)
                self.observability.increment("quarantined")
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            self.auditor.record(event="RECOVERY_SCAN", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="PENDING")
            order = self.repository.get_order(record.client_order_id)
            if order is None:
                reason = "durable order missing"
                self.observability.increment("quarantined")
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            intent = OrderIntent(record.client_order_id, order["symbol"], order["side"], float(order["quantity"]), record.broker_account_id, record.broker_route, record.idempotency_key)
            started = monotonic()
            try:
                self.auditor.record(event="BROKER_LOOKUP", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="LOOKUP")
                result: BrokerSubmissionResult = self.recovery.recover(intent)
                self.observability.observe_latency("recovery_latency", (monotonic() - started) * 1000)
                self.repository.mark_submission_submitted(record.idempotency_key, result.broker_order_id)
                if self.recovery.adapter.find_by_idempotency_key(intent).status.value == "FOUND":
                    self.observability.increment("recovery_found")
                    self.observability.increment("duplicate_preventions")
                else:
                    self.observability.increment("recovery_safe_retries")
                self.observability.increment("submitted")
                self.auditor.record(event="SUBMITTED", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="SUBMITTED", broker_order_id=result.broker_order_id)
                results.append(RecoveryResult(record.idempotency_key, "SUBMITTED", result.broker_order_id))
            except RuntimeError as exc:
                self.observability.observe_latency("recovery_latency", (monotonic() - started) * 1000)
                reason = str(exc)
                self.observability.increment("quarantined")
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
        return results
