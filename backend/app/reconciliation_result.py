from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.broker_execution_context import BrokerExecutionContext

_VERIFICATION_TOKEN = object()


@dataclass(frozen=True, init=False)
class ReconciliationResult:
    """Immutable broker reconciliation result bound to one authenticated execution context."""

    context: BrokerExecutionContext
    reconciled_at: datetime
    open_orders_reconciled: bool
    positions_reconciled: bool
    submission_intents_resolved: int
    broker_ready: bool
    _verification_token: object

    def __init__(self, *, context: BrokerExecutionContext, reconciled_at: datetime, open_orders_reconciled: bool, positions_reconciled: bool, submission_intents_resolved: int, broker_ready: bool, _verification_token: object) -> None:
        if _verification_token is not _VERIFICATION_TOKEN:
            raise TypeError("use ReconciliationResult.from_verified_check")
        if reconciled_at.tzinfo is None:
            raise ValueError("reconciled_at must be timezone-aware")
        if submission_intents_resolved < 0:
            raise ValueError("submission_intents_resolved must be non-negative")
        if not broker_ready:
            raise ValueError("broker must be ready for a verified reconciliation")
        if not open_orders_reconciled or not positions_reconciled:
            raise ValueError("open orders and positions must be reconciled")
        if reconciled_at > context.observed_at:
            raise ValueError("reconciled_at cannot be later than execution context observation")
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "reconciled_at", reconciled_at)
        object.__setattr__(self, "open_orders_reconciled", bool(open_orders_reconciled))
        object.__setattr__(self, "positions_reconciled", bool(positions_reconciled))
        object.__setattr__(self, "submission_intents_resolved", submission_intents_resolved)
        object.__setattr__(self, "broker_ready", bool(broker_ready))
        object.__setattr__(self, "_verification_token", _VERIFICATION_TOKEN)

    @property
    def account_id(self) -> str:
        return self.context.account_id

    @property
    def generation(self) -> int:
        return self.context.generation

    @property
    def broker_snapshot_fingerprint(self) -> str:
        return self.context.snapshot_fingerprint

    @classmethod
    def from_verified_check(cls, *, context: BrokerExecutionContext, reconciled_at: datetime, open_orders_reconciled: bool, positions_reconciled: bool, submission_intents_resolved: int, broker_ready: bool, _check_token: object) -> "ReconciliationResult":
        if not _check_token_is_valid(_check_token):
            raise TypeError("authenticated reconciliation check is required")
        return cls(context=context, reconciled_at=reconciled_at, open_orders_reconciled=open_orders_reconciled, positions_reconciled=positions_reconciled, submission_intents_resolved=submission_intents_resolved, broker_ready=broker_ready, _verification_token=_VERIFICATION_TOKEN)

    @property
    def verified(self) -> bool:
        return self._verification_token is _VERIFICATION_TOKEN


def _check_token_is_valid(token: object) -> bool:
    from app.reconciliation import _CHECK_TOKEN
    return token is _CHECK_TOKEN
