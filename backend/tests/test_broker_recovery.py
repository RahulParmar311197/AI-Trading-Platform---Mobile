from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_recovery import BrokerStartupRecovery
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
from app.safety_state import SafetyStateStore


class SnapshotBroker(BrokerAdapter):
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def submit_order(self, order):
        raise NotImplementedError

    def cancel_order(self, broker_order_id):
        raise NotImplementedError

    def get_order(self, broker_order_id):
        raise NotImplementedError

    def get_orders(self):
        return self.snapshot.orders

    def get_positions(self):
        return self.snapshot.positions

    def get_account(self):
        return {"status": "READY"}

    def get_snapshot(self):
        return self.snapshot


def test_router_snapshot_reaches_recovery(tmp_path):
    snapshot = BrokerSnapshot(
        orders=[{"client_order_id": "missing", "status": "FILLED"}],
        positions=[],
    )
    router = BrokerRouter([BrokerRoute("test", SnapshotBroker(snapshot))], "test")
    manager = BrokerStartupRecovery(
        router,
        ExecutionStateStore(str(tmp_path / "execution.json")),
        SafetyStateStore(str(tmp_path / "safety.json")),
    )
    result = manager.run(OrderLifecycle())
    assert result.ready is False
    assert result.reason == "BROKER_STATE_DRIFT"


def test_matching_empty_snapshot_is_ready(tmp_path):
    snapshot = BrokerSnapshot(orders=[], positions=[])
    router = BrokerRouter([BrokerRoute("test", SnapshotBroker(snapshot))], "test")
    manager = BrokerStartupRecovery(
        router,
        ExecutionStateStore(str(tmp_path / "execution.json")),
        SafetyStateStore(str(tmp_path / "safety.json")),
    )
    result = manager.run(OrderLifecycle())
    assert result.ready is True
    assert result.reason == "RECOVERY_OK"
