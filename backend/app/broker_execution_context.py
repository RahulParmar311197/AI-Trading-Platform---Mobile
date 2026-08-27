from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BrokerExecutionContext:
    """Atomic identity of the broker state being authorized for execution."""

    account_id: str
    broker_route: str
    route_generation: str
    generation: int
    snapshot_fingerprint: str
    observed_at: datetime
    attestation: str = ""

    def __post_init__(self) -> None:
        if not self.account_id.strip():
            raise ValueError("account_id is required")
        if not self.broker_route.strip():
            raise ValueError("broker_route is required")
        if not self.route_generation.strip():
            raise ValueError("route_generation is required")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if not self.snapshot_fingerprint.strip():
            raise ValueError("snapshot_fingerprint is required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("observed_at cannot be in the future")
        if not isinstance(self.attestation, str):
            raise ValueError("attestation must be a string")

    @property
    def canonical_key(self) -> tuple[str, str, str, int, str]:
        return (
            self.account_id,
            self.broker_route,
            self.route_generation,
            self.generation,
            self.snapshot_fingerprint,
        )
