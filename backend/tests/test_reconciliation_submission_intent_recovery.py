import pytest

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation import ReconciliationEngine
from app.reconciliation_coordinator import ReconciliationCoordinator
from app.submission_intent_store import SubmissionIntentStore


SECRET = b"t" * 32


def _intent(store):
    store.create(
        client_order_id="c1",
        route="paper",
        account_id="paper-account",
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        request_fingerprint="fp-c1",
    )


def _coordinator(store):
    return ReconciliationCoordinator(
        engine=ReconciliationEngine(store),
        route="paper",
        account_id="paper-account",
        route_generation="paper-1",
        context_attestor=BrokerContextAttestor(SECRET),
    )


def test_coordinator_recovers_matching_intent_from_authoritative_snapshot(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    _intent(store)

    snapshot = BrokerSnapshot(
        orders=[{
            "client_order_id": "c1",
            "order_id": "broker-1",
            "status": "NEW",
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 10,
            "filled_quantity": 0,
        }],
        positions=[],
        broker_route="paper",
        broker_account_id="paper-account",
    )

    result = _coordinator(store).reconcile(
        internal_orders=[{"client_order_id": "c1", "status": "NEW", "quantity": 10, "filled_quantity": 0}],
        internal_positions=[],
        broker_snapshot=snapshot,
    )

    assert result.verified is True
    assert result.submission_intents_resolved == 1
    assert store.unresolved_count() == 0


def test_coordinator_keeps_missing_intent_unresolved_and_fails_closed(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    _intent(store)

    snapshot = BrokerSnapshot(
        orders=[{"client_order_id": "other", "order_id": "broker-2", "status": "NEW"}],
        positions=[],
        broker_route="paper",
        broker_account_id="paper-account",
    )

    with pytest.raises(ValueError, match="unresolved submission intent"):
        _coordinator(store).reconcile(
            internal_orders=[],
            internal_positions=[],
            broker_snapshot=snapshot,
        )
    assert store.unresolved_count() == 1


def test_coordinator_rejects_ambiguous_intent_recovery(tmp_path):
    store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    _intent(store)

    snapshot = BrokerSnapshot(
        orders=[
            {"client_order_id": "c1", "order_id": "broker-1", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 10},
            {"client_order_id": "c1", "order_id": "broker-2", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 10},
        ],
        positions=[],
        broker_route="paper",
        broker_account_id="paper-account",
    )

    with pytest.raises(RuntimeError, match="duplicate broker client order id"):
        _coordinator(store).reconcile(
            internal_orders=[{"client_order_id": "c1", "status": "NEW", "quantity": 10, "filled_quantity": 0}],
            internal_positions=[],
            broker_snapshot=snapshot,
        )
    assert store.unresolved_count() == 1
