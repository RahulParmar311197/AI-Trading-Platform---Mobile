from datetime import datetime, timezone

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext


SECRET = b"s" * 32


def _context(attestation=""):
    return BrokerExecutionContext(
        account_id="acct",
        broker_route="upstox",
        route_generation="route-1",
        generation=4,
        snapshot_fingerprint="snapshot-1",
        observed_at=datetime.now(timezone.utc),
        attestation=attestation,
    )


def test_attestation_verifies_exact_context():
    attestor = BrokerContextAttestor(SECRET)
    context = _context()
    signature = attestor.sign(
        account_id=context.account_id,
        broker_route=context.broker_route,
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
    )
    signed = _context(signature)
    assert attestor.verify(signed)


def test_attestation_rejects_context_mutation():
    attestor = BrokerContextAttestor(SECRET)
    context = _context()
    signature = attestor.sign(
        account_id=context.account_id,
        broker_route=context.broker_route,
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
    )
    mutated = BrokerExecutionContext(
        account_id=context.account_id,
        broker_route="different-route",
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
        attestation=signature,
    )
    assert not attestor.verify(mutated)


def test_attestation_requires_strong_secret():
    try:
        BrokerContextAttestor(b"short")
    except ValueError:
        return
    raise AssertionError("short secrets must be rejected")
