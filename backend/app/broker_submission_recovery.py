from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.order_submission_service import BrokerSubmissionResult, OrderIntent


class BrokerLookupStatus(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class BrokerLookupResult:
    status: BrokerLookupStatus
    result: BrokerSubmissionResult | None = None


class RecoverableBrokerAdapter(Protocol):
    def find_by_idempotency_key(self, intent: OrderIntent) -> BrokerLookupResult: ...
    def submit_idempotent(self, intent: OrderIntent) -> BrokerSubmissionResult: ...


class SubmissionRecoveryService:
    """Recover an uncertain broker submission without blindly duplicating a live order."""

    def __init__(self, adapter: RecoverableBrokerAdapter) -> None:
        self.adapter = adapter

    def recover(self, intent: OrderIntent) -> BrokerSubmissionResult:
        lookup = self.adapter.find_by_idempotency_key(intent)
        if lookup.status is BrokerLookupStatus.FOUND and lookup.result is not None:
            return lookup.result
        if lookup.status is BrokerLookupStatus.AMBIGUOUS:
            raise RuntimeError("broker submission is ambiguous; quarantine/manual reconciliation required")
        return self.adapter.submit_idempotent(intent)
