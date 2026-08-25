from __future__ import annotations

from dataclasses import dataclass

from app.broker_submission_recovery import SubmissionRecoveryService
from app.order_submission_service import OrderIntent
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class RecoveryOutcome:
    idempotency_key: str
    status: str
    broker_order_id: str | None = None


class DurableSubmissionRecovery:
    """Recover durable PENDING submissions without duplicating broker orders."""

    def __init__(self, repository: TransactionalExecutionRepository, recovery: SubmissionRecoveryService) -> None:
        self.repository = repository
        self.recovery = recovery

    def _intent_for_submission(self, record) -> OrderIntent:
        with self.repository._lock:
            row = self.repository._db.execute(
                "SELECT symbol,side,quantity,broker_account_id,broker_route FROM orders WHERE order_id=?",
                (record.client_order_id,),
            ).fetchone()
        if row is None:
            raise KeyError(record.client_order_id)
        symbol, side, quantity, account_id, route = row
        if account_id != record.broker_account_id or route != record.broker_route:
            raise ValueError("durable submission scope does not match order scope")
        return OrderIntent(
            client_order_id=record.client_order_id,
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            broker_account_id=record.broker_account_id,
            broker_route=record.broker_route,
            idempotency_key=record.idempotency_key,
        )

    def recover_pending(self, *, limit: int = 100) -> list[RecoveryOutcome]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        outcomes: list[RecoveryOutcome] = []
        for record in self.repository.pending_submissions(limit=limit):
            try:
                intent = self._intent_for_submission(record)
                result = self.recovery.recover(intent)
            except RuntimeError:
                outcomes.append(RecoveryOutcome(record.idempotency_key, "QUARANTINED"))
                continue
            self.repository.mark_submission_submitted(record.idempotency_key, result.broker_order_id)
            outcomes.append(RecoveryOutcome(record.idempotency_key, "SUBMITTED", result.broker_order_id))
        return outcomes
