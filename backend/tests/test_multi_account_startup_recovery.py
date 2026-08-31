from app.broker_context_attestation import BrokerContextAttestor
from app.broker_snapshot import BrokerSnapshot
from app.multi_account_startup_recovery import MultiAccountStartupRecovery
from app.order_lifecycle import OrderLifecycle, PositionRecord
from app.reconciliation import ReconciliationEngine
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


class FakeExecutionStore:
    def load(self, lifecycle):
        return None


class FakeRouter:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.reconciliation_engine = None

    def get(self, route):
        account_id = route.rsplit(":", 1)[-1]
        return type("Route", (), {
            "name": route,
            "broker_account_id": account_id,
            "generation": f"generation-{account_id}",
        })()

    def get_snapshot(self, route):
        return self.snapshots[route]

    @staticmethod
    def _next_reconciliation_generation(selected):
        return 1


def _recovery(tmp_path, snapshots):
    intent_store = SubmissionIntentStore(str(tmp_path / "intents.json"))
    engine = ReconciliationEngine(intent_store)
    router = FakeRouter(snapshots)
    router.reconciliation_engine = engine
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    return MultiAccountStartupRecovery(
        router,
        FakeExecutionStore(),
        safety,
        BrokerContextAttestor(b"x" * 32),
    ), safety


def _account(account_id, broker="upstox"):
    return type("Account", (), {"id": account_id, "broker": broker})()


def test_all_accounts_are_reconciled_independently(tmp_path):
    accounts = [_account(101), _account(202)]
    snapshots = {
        "upstox:account:101": BrokerSnapshot([], [], broker_route="upstox:account:101", broker_account_id=101),
        "upstox:account:202": BrokerSnapshot([], [], broker_route="upstox:account:202", broker_account_id=202),
    }
    recovery, safety = _recovery(tmp_path, snapshots)

    result = recovery.run(OrderLifecycle(), accounts)

    assert result.ready is True
    assert [item.account_id for item in result.accounts] == ["101", "202"]
    assert all(item.ready for item in result.accounts)
    # Recovery is phase one only; the outer startup gate owns the final release.
    assert safety.load().trading_halted is True


def test_wrong_account_snapshot_fails_closed(tmp_path):
    accounts = [_account(101), _account(202)]
    snapshots = {
        "upstox:account:101": BrokerSnapshot([], [], broker_route="upstox:account:101", broker_account_id=202),
        "upstox:account:202": BrokerSnapshot([], [], broker_route="upstox:account:202", broker_account_id=202),
    }
    recovery, safety = _recovery(tmp_path, snapshots)

    result = recovery.run(OrderLifecycle(), accounts)

    assert result.ready is False
    assert result.reason == "MULTI_ACCOUNT_RECONCILIATION_FAILED"
    assert any(not item.ready for item in result.accounts)
    assert safety.load().trading_halted is True


def test_unscoped_persisted_position_is_rejected(tmp_path):
    lifecycle = OrderLifecycle()
    lifecycle.positions["RELIANCE"] = PositionRecord(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        entry_price=2500,
        broker_account_id=None,
        broker_route=None,
    )
    accounts = [_account(101), _account(202)]
    snapshots = {
        "upstox:account:101": BrokerSnapshot([], [], broker_route="upstox:account:101", broker_account_id=101),
        "upstox:account:202": BrokerSnapshot([], [], broker_route="upstox:account:202", broker_account_id=202),
    }
    recovery, safety = _recovery(tmp_path, snapshots)

    result = recovery.run(lifecycle, accounts)

    assert result.ready is False
    assert result.reason.startswith("MULTI_ACCOUNT_STATE_UNSCOPED")
    assert safety.load().trading_halted is True
