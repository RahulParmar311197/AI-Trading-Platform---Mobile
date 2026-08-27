from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from datetime import datetime


@dataclass(frozen=True)
class BrokerContextAttestor:
    """Signs and verifies broker execution contexts produced by reconciliation."""

    secret: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("broker context attestation secret must contain at least 32 bytes")

    def sign(
        self,
        *,
        account_id: str,
        broker_route: str,
        route_generation: str,
        generation: int,
        snapshot_fingerprint: str,
        observed_at: datetime,
    ) -> str:
        payload = _payload(
            account_id,
            broker_route,
            route_generation,
            generation,
            snapshot_fingerprint,
            observed_at,
        )
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, context: object) -> bool:
        try:
            expected = self.sign(
                account_id=context.account_id,
                broker_route=context.broker_route,
                route_generation=context.route_generation,
                generation=context.generation,
                snapshot_fingerprint=context.snapshot_fingerprint,
                observed_at=context.observed_at,
            )
            return hmac.compare_digest(expected, context.attestation)
        except (AttributeError, TypeError, ValueError):
            return False


def _payload(
    account_id: str,
    broker_route: str,
    route_generation: str,
    generation: int,
    snapshot_fingerprint: str,
    observed_at: datetime,
) -> bytes:
    return "|".join(
        (
            account_id,
            broker_route,
            route_generation,
            str(generation),
            snapshot_fingerprint,
            observed_at.isoformat(),
        )
    ).encode("utf-8")
