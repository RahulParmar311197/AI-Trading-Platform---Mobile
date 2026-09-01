import pytest

from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


class AuthoritativeSnapshot(BrokerSnapshot):
    def require_authoritative(self):
        return self.orders


class SnapshotBroker:
    def __init__(self, orders):
        self.orders = list(orders)

    def get_order_snapshot(self):
        return AuthoritativeSnapshot(orders=list(self.orders), positions=[])


def _router(tmp_path, orders):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    intents = SubmissionIntentStore(str(tmp_path / "intents.json"))
    broker = SnapshotBroker(orders)
    router = BrokerRouter(
        [BrokerRoute("paper", broker)],
        "paper",
        safety_store=safety,
        submission_intent_store=intents,
    )
    return router, intents, safety


def fingerprint(client_id):
    return f"fingerprint-{client_id}"


def _intent(intents, client_id="client-1", account_id="acct-1"):
    return intents.create(
        client_order_id=client_id,
        route="paper",
        account_id=account_id,
        symbol="NIFTY",
        side="BUY",
        quantity=2,
        request_fingerprint=fingerprint(client_id),
    )


def test_recovery_requires_exactly_one_broker_match(tmp_path):
    router, intents, safety = _router(tmp_path, [{"client_order_id": "other", "order_id": "broker-1", "status": "NEW"}])
    _intent(intents)

    resolved = router.reconcile_unresolved_submission_intents()

    assert resolved == []
    assert intents.unresolved_count() == 1
    assert safety.load().trading_halted is True


def test_recovery_rejects_duplicate_broker_matches(tmp_path):
    orders = [
        {"client_order_id": "client-1", "order_id": "broker-1", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 2},
        {"client_order_id": "client-1", "order_id": "broker-2", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 2},
    ]
    router, intents, safety = _router(tmp_path, orders)
    _intent(intents)

    with pytest.raises(RuntimeError, match="ambiguous unresolved submission intent"):
        router.reconcile_unresolved_submission_intents()

    assert intents.unresolved_count() == 1
    assert safety.load().trading_halted is True


def test_recovery_rejects_account_mismatch(tmp_path):
    router, intents, safety = _router(tmp_path, [{"client_order_id": "client-1", "order_id": "broker-1", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 2}])
    _intent(intents, account_id="acct-other")
    router.routes["paper"] = BrokerRoute("paper", router.routes["paper"].adapter, broker_account_id="acct-1", generation="gen-1")

    with pytest.raises(RuntimeError, match="account mismatch"):
        router.reconcile_unresolved_submission_intents()

    assert intents.unresolved_count() == 1
    assert safety.load().trading_halted is True


def test_recovery_rejects_payload_identity_mismatch(tmp_path):
    router, intents, safety = _router(tmp_path, [{"client_order_id": "client-1", "order_id": "broker-1", "status": "NEW", "symbol": "BANKNIFTY", "side": "BUY", "quantity": 2}])
    _intent(intents)

    with pytest.raises(RuntimeError, match="payload mismatch"):
        router.reconcile_unresolved_submission_intents()

    assert intents.unresolved_count() == 1
    assert safety.load().trading_halted is True


def test_recovery_rejects_incomplete_broker_identity_before_resolution(tmp_path):
    router, intents, safety = _router(tmp_path, [{"client_order_id": "client-1", "order_id": "", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 2}])
    _intent(intents)

    with pytest.raises(RuntimeError, match="incomplete broker recovery payload"):
        router.reconcile_unresolved_submission_intents()

    assert intents.unresolved_count() == 1
    assert safety.load().trading_halted is True


def test_recovery_binds_and_resolves_one_valid_match(tmp_path):
    router, intents, safety = _router(tmp_path, [{"client_order_id": "client-1", "order_id": "broker-1", "status": "NEW", "symbol": "NIFTY", "side": "BUY", "quantity": 2}])
    _intent(intents)

    assert router.reconcile_unresolved_submission_intents() == ["client-1"]
    assert intents.unresolved_count() == 0
    assert safety.load().trading_halted is False
    assert intents.get_unresolved("client-1") is None
