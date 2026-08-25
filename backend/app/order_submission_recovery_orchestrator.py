from __future__ import annotations

from dataclasses import dataclass

from app.broker_submission_recovery import SubmissionRecoveryService
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
    """Canonical restart path for durable PENDING outbound orders with mandatory audit and authorization."""

    def __init__(
        self,
        repository: TransactionalExecutionRepository,
        recovery: SubmissionRecoveryService,
        auditor: SubmissionRecoveryAuditor | None = None,
        authorizer: RecoveryAuthorizer | None = None,
    ) -> None:
        self.repository = repository
        self.recovery = recovery
        self.auditor = auditor or SubmissionRecoveryAuditor()
        if authorizer is None:
            raise ValueError("recovery authorizer is required")
        self.authorizer = authorizer

    def recover_pending(self, *, limit: int = 100, approval: RecoveryApproval) -> list[RecoveryResult]:
        results: list[RecoveryResult] = []
        for record in self.repository.pending_submissions(limit=limit):
            if approval.broker_account_id != record.broker_account_id or approval.broker_route != record.broker_route:
                reason = "recovery approval is outside broker account scope"
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            try:
                self.authorizer.authorize(approval)
            except PermissionError as exc:
                reason = str(exc)
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            self.auditor.record(event="RECOVERY_SCAN", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="PENDING")
            order = self.repository.get_order(record.client_order_id)
            if order is None:
                reason = "durable order missing"
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
                continue
            intent = OrderIntent(record.client_order_id, order["symbol"], order["side"], float(order["quantity"]), record.broker_account_id, record.broker_route, record.idempotency_key)
            try:
                self.auditor.record(event="BROKER_LOOKUP", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="LOOKUP")
                result: BrokerSubmissionResult = self.recovery.recover(intent)
                self.repository.mark_submission_submitted(record.idempotency_key, result.broker_order_id)
                self.auditor.record(event="SUBMITTED", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="SUBMITTED", broker_order_id=result.broker_order_id)
                results.append(RecoveryResult(record.idempotency_key, "SUBMITTED", result.broker_order_id))
            except RuntimeError as exc:
                reason = str(exc)
                self.auditor.record(event="QUARANTINE", idempotency_key=record.idempotency_key, client_order_id=record.client_order_id, status="QUARANTINED", reason=reason)
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=reason))
        return results
