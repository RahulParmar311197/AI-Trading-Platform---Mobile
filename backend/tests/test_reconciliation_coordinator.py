from datetime import datetime, timezone

import pytest

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation import ReconciliationEngine
from app.reconciliation_coordinator import ReconciliationCoordinator
from app.submission_intent_store import SubmissionIntentStore


SECRET = b"t" * 32


def _coordinator(tmp_path, generation=3):
    return ReconciliationCoordinator(
        engine=ReconciliationEngine(SubmissionIntentStore(str(tmp_path / "intents.json"))),
        route="paper",
        account_id="paper-account",
        route_generation="paper-1",
        context_attestor=BrokerContextAttestor(SECRET),
        generation=generation,
    )


def _snapshot(quantity=0):
    return BrokerSnapshot(
        orders=[{"client_order_id": "c1", "status": "NEW", "quantity": 10, "filled_quantity": 0}],
        positions=[{"symbol": "NIFTY", "quantity": quantity, "side": "BUY"}],
        broker_route="paper",
        broker_account_id="paper-account",
    )


def test_coordinator_builds_attested_verified_result_from_one_supplied_snapshot(tmp_path):
    result = _coordinator(tmp_path).reconcile(
        internal_orders=[{"client_order_id": "c1", "status": "NEW", "quantity": 10, "filled_quantity": 0}],
        internal_positions=[{"symbol": "NIFTY", "quantity": 0, "side": "BUY"}],
        broker_snapshot=_snapshot(),
    )
    assert result.context.account_id == "paper-account"
    assert result.context.broker_route == "paper"
    assert result.context.route_generation == "paper-1"
    assert result.context.generation == 3
    assert result.context.snapshot_fingerprint == _snapshot().fingerprint()
    assert BrokerContextAttestor(SECRET).verify(result.context)
    assert result.verified is True


def test_coordinator_rejects_snapshot_route_mismatch(tmp_path):
    snapshot = _snapshot()
    mismatched = BrokerSnapshot(snapshot.orders, snapshot.positions, "upstox", "paper-account")
    with pytest.raises(ValueError, match="route"):
        _coordinator(tmp_path).reconcile(internal_orders=[], internal_positions=[], broker_snapshot=mismatched)


def test_coordinator_rejects_snapshot_account_mismatch(tmp_path):
    snapshot = _snapshot()
    mismatched = BrokerSnapshot(snapshot.orders, snapshot.positions, "paper", "other-account")
    with pytest.raises(ValueError, match="account"):
        _coordinator(tmp_path).reconcile(internal_orders=[], internal_positions=[], broker_snapshot=mismatched)


def test_coordinator_fails_closed_on_reconciliation_mismatch(tmp_path):
    snapshot = _snapshot(quantity=1)
    with pytest.raises(RuntimeError, match="reconciliation failed"):
        _coordinator(tmp_path).reconcile(
            internal_orders=[{"client_order_id": "c1", "status": "NEW", "quantity": 10, "filled_quantity": 0}],
            internal_positions=[{"symbol": "NIFTY", "quantity": 0, "side": "BUY"}],
            broker_snapshot=snapshot,
        )


def test_coordinator_rejects_naive_engine_timestamp(tmp_path):
    class NaiveEngine:
        def check(self, *args):
            class Check:
                ok = True
                trading_halted = False
                checked_at = "2026-08-29T10:00:00"
            return Check()

        def build_verified_result(self, check, **kwargs):
            return kwargs

    with pytest.raises(ValueError, match="timezone-aware"):
        ReconciliationCoordinator(
            engine=NaiveEngine(), route="paper", account_id="paper-account",
            route_generation="paper-1", context_attestor=BrokerContextAttestor(SECRET), generation=3,
        ).reconcile(internal_orders=[], internal_positions=[], broker_snapshot=_snapshot())
