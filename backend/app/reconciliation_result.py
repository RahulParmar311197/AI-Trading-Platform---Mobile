from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ReconciliationResult:
    """Verified broker reconciliation result required to unlock trading."""

    account_id: str
    generation: int
    reconciled_at: datetime
    open_orders_reconciled: bool
    positions_reconciled: bool
    submission_intents_resolved: int
    broker_ready: bool

    def __post_init__(self) -> None:
        if not self.account_id.strip():
            raise ValueError("account_id is required")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if self.reconciled_at.tzinfo is None:
            raise ValueError("reconciled_at must be timezone-aware")
        if self.reconciled_at > datetime.now(timezone.utc):
            raise ValueError("reconciled_at cannot be in the future")
        if self.submission_intents_resolved < 0:
            raise ValueError("submission_intents_resolved must be non-negative")
        if not self.broker_ready:
            raise ValueError("broker must be ready for a verified reconciliation")
        if not self.open_orders_reconciled or not self.positions_reconciled:
            raise ValueError("open orders and positions must be reconciled")

    @property
    def verified(self) -> bool:
        return True
