from __future__ import annotations

from dataclasses import dataclass

from app.canonical_execution_dispatcher import CanonicalExecutionDispatcher
from app.execution_quarantine_recovery import ExecutionQuarantineRecovery, RecoveryResult
from app.order_identity_registry import OrderIdentity, OrderIdentityRegistry
from app.execution_event_quarantine import ExecutionEventQuarantine
from app.transactional_execution_repository import TransactionalExecutionRepository


@dataclass(frozen=True)
class IdentityMatch:
    broker: str
    broker_order_id: str
    client_order_id: str
    broker_account_id: int | None = None
    broker_route: str | None = None


class ReconciliationEventRecovery:
    """Bind only explicitly reconciled identities, then recover quarantined events."""

    def __init__(self, registry: OrderIdentityRegistry, quarantine: ExecutionEventQuarantine, repository: TransactionalExecutionRepository) -> None:
        self.registry = registry
        self.quarantine = quarantine
        self.repository = repository

    def bind_reconciled_identity(self, match: IdentityMatch) -> None:
        self.registry.bind(OrderIdentity(match.client_order_id, match.broker, match.broker_order_id, match.broker_account_id, match.broker_route))

    def recover(self, limit: int = 100) -> RecoveryResult:
        worker = ExecutionQuarantineRecovery(self.registry, self.quarantine, CanonicalExecutionDispatcher(self.repository))
        return worker.recover(limit)
