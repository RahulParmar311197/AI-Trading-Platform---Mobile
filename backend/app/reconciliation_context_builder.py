from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .broker_context_attestation import BrokerContextAttestor
from .broker_execution_context import BrokerExecutionContext
from .reconciliation_snapshot import ReconciliationSnapshot, next_snapshot


@dataclass
class ReconciliationContextBuilder:
    account_id: str
    broker_route: str
    route_generation: str
    attestor: BrokerContextAttestor
    previous: ReconciliationSnapshot | None = None

    def build(
        self,
        *,
        positions: Sequence[Mapping[str, Any]],
        orders: Sequence[Mapping[str, Any]] = (),
        observed_at: datetime | None = None,
    ) -> BrokerExecutionContext:
        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        snapshot = next_snapshot(self.previous, positions=positions, orders=orders)
        self.previous = snapshot
        unsigned = BrokerExecutionContext(
            account_id=self.account_id,
            broker_route=self.broker_route,
            route_generation=self.route_generation,
            generation=snapshot.generation,
            snapshot_fingerprint=snapshot.fingerprint,
            observed_at=observed_at,
        )
        signature = self.attestor.sign(
            account_id=unsigned.account_id,
            broker_route=unsigned.broker_route,
            route_generation=unsigned.route_generation,
            generation=unsigned.generation,
            snapshot_fingerprint=unsigned.snapshot_fingerprint,
            observed_at=unsigned.observed_at,
        )
        return BrokerExecutionContext(
            account_id=unsigned.account_id,
            broker_route=unsigned.broker_route,
            route_generation=unsigned.route_generation,
            generation=unsigned.generation,
            snapshot_fingerprint=unsigned.snapshot_fingerprint,
            observed_at=unsigned.observed_at,
            attestation=signature,
        )
