from __future__ import annotations

from datetime import datetime
from typing import Any

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation import ReconciliationEngine
from app.reconciliation_result import ReconciliationResult
from app.submission_intent_store import SubmissionIntentStore


class ReconciliationCoordinator:
    """Capture one authoritative broker state and turn it into a verified result."""

    def __init__(
        self,
        *,
        engine: ReconciliationEngine,
        route: str,
        account_id: str,
        route_generation: str,
        context_attestor: BrokerContextAttestor,
        generation: int = 0,
        submission_intent_store: SubmissionIntentStore | None = None,
    ) -> None:
        if not route.strip():
            raise ValueError("route is required")
        if not account_id.strip():
            raise ValueError("account_id is required")
        if not route_generation.strip():
            raise ValueError("route_generation is required")
        if generation < 0:
            raise ValueError("generation must be non-negative")
        if not isinstance(context_attestor, BrokerContextAttestor):
            raise ValueError("context attestor is required")
        self.engine = engine
        self.route = route
        self.account_id = str(account_id).strip()
        self.route_generation = str(route_generation).strip()
        self.context_attestor = context_attestor
        self.generation = generation
        self.submission_intent_store = submission_intent_store or engine.submission_intent_store
        if self.submission_intent_store is None:
            raise ValueError("durable submission intent store is required")

    def reconcile(
        self,
        *,
        internal_orders: list[dict[str, Any]],
        internal_positions: list[dict[str, Any]],
        broker_snapshot: BrokerSnapshot,
        broker_ready: bool = True,
    ) -> ReconciliationResult:
        """Use the supplied authoritative snapshot as the sole broker observation."""
        if broker_snapshot.broker_route != self.route:
            raise ValueError("broker snapshot route does not match reconciliation route")
        if broker_snapshot.broker_account_id is None or str(broker_snapshot.broker_account_id) != self.account_id:
            raise ValueError("broker snapshot account does not match reconciliation account")
        check = self.engine.check(
            internal_orders,
            broker_snapshot.orders,
            internal_positions,
            broker_snapshot.positions,
            broker_account_id=self.account_id,
            broker_route=self.route,
        )
        if not check.ok or check.trading_halted:
            raise RuntimeError("broker reconciliation failed; trading remains halted")
        observed_at = datetime.fromisoformat(check.checked_at)
        if observed_at.tzinfo is None:
            raise ValueError("reconciliation observation must be timezone-aware")
        fingerprint = broker_snapshot.fingerprint()
        attestation = self.context_attestor.sign(
            account_id=self.account_id,
            broker_route=self.route,
            route_generation=self.route_generation,
            generation=self.generation,
            snapshot_fingerprint=fingerprint,
            observed_at=observed_at,
        )
        context = BrokerExecutionContext(
            account_id=self.account_id,
            broker_route=self.route,
            route_generation=self.route_generation,
            generation=self.generation,
            snapshot_fingerprint=fingerprint,
            observed_at=observed_at,
            attestation=attestation,
        )
        resolved = self.submission_intent_store.recover_from_broker_orders(broker_snapshot.orders)
        return self.engine.build_verified_result(
            check,
            context=context,
            reconciled_at=observed_at,
            open_orders_reconciled=True,
            positions_reconciled=True,
            submission_intents_resolved=resolved,
            broker_ready=broker_ready,
        )
