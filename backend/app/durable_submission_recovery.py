from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker_submission_recovery import SubmissionRecoveryService
from app.order_submission_service import OrderIntent
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class RecoveryOutcome:
    idempotency_key: str
    status: str
    broker_order_id: str | None = None


class DurableSubmissionRecovery:
    """Recover durable PENDING submissions through broker lookup, never blind retry."""

    def __init__(self, repository: TransactionalExecutionRepository, recovery: SubmissionRecoveryService) -> None:
        self.repository = repository
        self.recovery = recovery

    def recover_pending(self, *, limit: int = 100) -> list[RecoveryOutcome]:
        outcomes: list[RecoveryOutcome] = []
        for row in self.repository.pending_submissions(limit=limit):
            intent = OrderIntent(
                row["client_order_id"], row["symbol"], row["side"], row["quantity"],
                row["broker_account_id"], row["broker_route"], row["idempotency_key"],
            )
            try:
                result = self.recovery.recover(intent)
            except RuntimeError:
                outcomes.append(RecoveryOutcome(row["idempotency_key"], "QUARANTINED"))
                continue
            self.repository.mark_submission_submitted(row["idempotency_key"], result.broker_order_id)
            outcomes.append(RecoveryOutcome(row["idempotency_key"], "SUBMITTED", result.broker_order_id))
        return outcomes
