from __future__ import annotations

from dataclasses import dataclass

from app.broker_submission_recovery import SubmissionRecoveryService
from app.order_submission_service import BrokerSubmissionResult, OrderIntent
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class RecoveryResult:
    idempotency_key: str
    status: str
    broker_order_id: str | None = None
    reason: str | None = None


class OrderSubmissionRecoveryOrchestrator:
    """Canonical restart path for durable PENDING outbound orders."""

    def __init__(self, repository: TransactionalExecutionRepository, recovery: SubmissionRecoveryService) -> None:
        self.repository = repository
        self.recovery = recovery

    def recover_pending(self, *, limit: int = 100) -> list[RecoveryResult]:
        results: list[RecoveryResult] = []
        for record in self.repository.pending_submissions(limit=limit):
            order = self.repository.get_order(record.client_order_id)
            if order is None:
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason="durable order missing"))
                continue
            intent = OrderIntent(record.client_order_id, order["symbol"], order["side"], float(order["quantity"]), record.broker_account_id, record.broker_route, record.idempotency_key)
            try:
                result: BrokerSubmissionResult = self.recovery.recover(intent)
                self.repository.mark_submission_submitted(record.idempotency_key, result.broker_order_id)
                results.append(RecoveryResult(record.idempotency_key, "SUBMITTED", result.broker_order_id))
            except RuntimeError as exc:
                results.append(RecoveryResult(record.idempotency_key, "QUARANTINED", reason=str(exc)))
        return results
