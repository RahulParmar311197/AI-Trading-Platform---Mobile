from datetime import datetime, timezone

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext


SECRET = b"s" * 32


def _context(**changes):
    values = dict(
        account_id="acct",
        broker_route="upstox",
        route_generation="route-1",
        generation=4,
        snapshot_fingerprint="snapshot-1",
        observed_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        attestation="",
    )
    values.update(changes)
    return BrokerExecutionContext(**values)


def _attest(context):
    attestor = BrokerContextAttestor(SECRET)
    signature = attestor.sign(
        account_id=context.account_id,
        broker_route=context.broker_route,
        route_generation=context.route_generation,
        generation=context.generation,
        snapshot_fingerprint=context.snapshot_fingerprint,
        observed_at=context.observed_at,
    )
    return _context(attestation=signature)


def test_attestation_verifies_exact_context():
    assert BrokerContextAttestor(SECRET).verify(_attest(_context()))


def test_attestation_rejects_context_mutation():
    signed = _attest(_context())
    mutated = _context(broker_route="different-route", attestation=signed.attestation)
    assert not BrokerContextAttestor(SECRET).verify(mutated)


def test_snapshot_fingerprint_fences_old_attestation():
    signed = _attest(_context())
    changed = _context(snapshot_fingerprint="snapshot-2", attestation=signed.attestation)
    assert not BrokerContextAttestor(SECRET).verify(changed)


def test_generation_fences_old_attestation():
    signed = _attest(_context())
    changed = _context(generation=5, attestation=signed.attestation)
    assert not BrokerContextAttestor(SECRET).verify(changed)


def test_route_generation_fences_old_attestation():
    signed = _attest(_context())
    changed = _context(route_generation="route-2", attestation=signed.attestation)
    assert not BrokerContextAttestor(SECRET).verify(changed)


def test_timestamp_fences_old_attestation():
    signed = _attest(_context())
    changed = _context(
        observed_at=datetime(2026, 8, 28, 12, 0, 1, tzinfo=timezone.utc),
        attestation=signed.attestation,
    )
    assert not BrokerContextAttestor(SECRET).verify(changed)


def test_wrong_secret_rejects_attestation():
    signed = _attest(_context())
    assert not BrokerContextAttestor(b"x" * 32).verify(signed)


def test_attestation_requires_strong_secret():
    try:
        BrokerContextAttestor(b"short")
    except ValueError:
        return
    raise AssertionError("short secrets must be rejected")
