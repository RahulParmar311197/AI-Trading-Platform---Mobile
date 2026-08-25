from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.execution_event_quarantine import ExecutionEventQuarantine
from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


class RecoveryClass(str, Enum):
    NO_DETERMINISTIC_MATCH = "NO_DETERMINISTIC_RECONCILIATION_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_RECONCILIATION_MATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class RecoveryCase:
    case_id: str
    broker: str
    broker_order_id: str
    broker_account_id: int
    broker_route: str
    classification: RecoveryClass
    payload: dict[str, Any]


class ReconciliationRecoveryControl:
    """Explicit, fail-closed recovery; never auto-binds ambiguous cases."""

    def __init__(self, repository: TransactionalExecutionRepository, quarantine: ExecutionEventQuarantine) -> None:
        self.repository = repository
        self.quarantine = quarantine

    def approve_bind(self, case: RecoveryCase, *, order_id: str, approver: str) -> None:
        if not approver:
            raise ValueError("approver is required")
        if case.classification is not RecoveryClass.MANUAL_REVIEW:
            raise ValueError("only manually reviewed cases may be approved")
        if case.broker_account_id <= 0 or not case.broker_route:
            raise ValueError("invalid recovery scope")
        identity = OrderIdentity(order_id, case.broker, case.broker_order_id, broker_account_id=case.broker_account_id, broker_route=case.broker_route)
        self.repository.bind_identity(identity)
        self.quarantine.resolve(self._quarantine_id(case))

    @staticmethod
    def _quarantine_id(case: RecoveryCase) -> int:
        value = case.payload.get("quarantine_id")
        if not isinstance(value, int) or value <= 0:
            raise ValueError("quarantine_id is required")
        return value
