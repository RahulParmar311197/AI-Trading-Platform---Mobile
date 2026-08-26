from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

_VERIFICATION_TOKEN = object()


@dataclass(frozen=True, init=False)
class ReconciliationResult:
    """Immutable broker reconciliation result created only by the verified factory."""

    account_id: str
    generation: int
    reconciled_at: datetime
    open_orders_reconciled: bool
    positions_reconciled: bool
    submission_intents_resolved: int
    broker_ready: bool
    _verification_token: object

    def __init__(
        self,
        *,
        account_id: str,
        generation: int,
        reconciled_at: datetime,
        open_orders_reconciled: bool,
        positions_reconciled: bool,
        submission_intents_resolved: int,
        broker_ready: bool,
        _verification_token: object,
    ) -> None:
        if _verification_token is not _VERIFICATION_TOKEN:
            raise TypeError("use ReconciliationResult.from_verified_state")
        if not account_id.strip():
            raise ValueError("account_id is required")
        if generation < 0:
            raise ValueError("generation must be non-negative")
        if reconciled_at.tzinfo is None:
            raise ValueError("reconciled_at must be timezone-aware")
        if reconciled_at > datetime.now(timezone.utc):
            raise ValueError("reconciled_at cannot be in the future")
        if submission_intents_resolved < 0:
            raise ValueError("submission_intents_resolved must be non-negative")
        if not broker_ready:
            raise ValueError("broker must be ready for a verified reconciliation")
        if not open_orders_reconciled or not positions_reconciled:
            raise ValueError("open orders and positions must be reconciled")
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "generation", generation)
        object.__setattr__(self, "reconciled_at", reconciled_at)
        object.__setattr__(self, "open_orders_reconciled", open_orders_reconciled)
        object.__setattr__(self, "positions_reconciled", positions_reconciled)
        object.__setattr__(self, "submission_intents_resolved", submission_intents_resolved)
        object.__setattr__(self, "broker_ready", broker_ready)
        object.__setattr__(self, "_verification_token", _VERIFICATION_TOKEN)

    @classmethod
    def from_verified_state(
        cls,
        *,
        account_id: str,
        generation: int,
        reconciled_at: datetime,
        open_orders_reconciled: bool,
        positions_reconciled: bool,
        submission_intents_resolved: int,
        broker_ready: bool,
    ) -> "ReconciliationResult":
        return cls(
            account_id=account_id,
            generation=generation,
            reconciled_at=reconciled_at,
            open_orders_reconciled=open_orders_reconciled,
            positions_reconciled=positions_reconciled,
            submission_intents_resolved=submission_intents_resolved,
            broker_ready=broker_ready,
            _verification_token=_VERIFICATION_TOKEN,
        )

    @property
    def verified(self) -> bool:
        return self._verification_token is _VERIFICATION_TOKEN
