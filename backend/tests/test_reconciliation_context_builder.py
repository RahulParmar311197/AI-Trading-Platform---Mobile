from datetime import datetime, timezone

from app.broker_context_attestation import BrokerContextAttestor
from app.reconciliation_context_builder import ReconciliationContextBuilder


def test_builder_creates_verifiable_context_and_fences_changes():
    attestor = BrokerContextAttestor(b"s" * 32)
    builder = ReconciliationContextBuilder("acct", "upstox", "route-1", attestor)
    observed = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    first = builder.build(positions=[{"symbol": "NIFTY", "quantity": 1}], observed_at=observed)
    same = builder.build(positions=[{"symbol": "NIFTY", "quantity": 1}], observed_at=observed)
    changed = builder.build(positions=[{"symbol": "NIFTY", "quantity": 2}], observed_at=observed)
    assert attestor.verify(first)
    assert same.generation == first.generation
    assert changed.generation == first.generation + 1
    assert changed.snapshot_fingerprint != first.snapshot_fingerprint


def test_builder_rejects_naive_timestamp():
    builder = ReconciliationContextBuilder("acct", "upstox", "route-1", BrokerContextAttestor(b"s" * 32))
    try:
        builder.build(positions=[], observed_at=datetime(2026, 8, 28, 12, 0))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamp must be rejected")
