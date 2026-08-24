import pytest

from app.broker_adapter import BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.risk_gate import PreTradeRiskGate, RiskLimits
from app.runtime_risk_snapshot import RuntimeRiskSnapshotProvider
from app.safety_state import SafetyStateStore
from app.startup_recovery import StartupRecoveryCoordinator


class Broker:
    def __init__(self, positions=None, account=None, snapshot=None):
        self.positions = positions or []
        self.account = account or {"status": "READY"}
        self.snapshot = snapshot

    def submit_order(self, request):
        raise AssertionError("submission must not be reached in these tests")

    def cancel_order(self, order_id):
        raise NotImplementedError

    def get_order(self, order_id):
        raise NotImplementedError

    def get_orders(self):
        return []

    def get_positions(self):
        return self.positions

    def get_account(self):
        return self.account

    def get_snapshot(self):
        if self.snapshot is not None:
            return self.snapshot
        return BrokerSnapshot(orders=[], positions=self.positions)


def request(symbol="NIFTY", side="BUY", quantity=5, security_id="NIFTY-SEC"):
    return BrokerOrderRequest(client_order_id="risk-runtime-1", symbol=symbol, side=side, quantity=quantity, security_id=security_id, price=100, stop=95)


def provider(tmp_path, positions=None, account=None, loss=10.0, snapshot=None, max_age=2.0):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = Broker(positions=positions, account=account, snapshot=snapshot)
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    return RuntimeRiskSnapshotProvider(router, lifecycle, trading_day_timezone="Asia/Kolkata", max_snapshot_age_seconds=max_age)


def test_snapshot_uses_signed_broker_position(tmp_path):
    p = provider(tmp_path, positions=[{"symbol": "NIFTY", "quantity": 8, "side": "SELL"}])
    snapshot = p(request(side="SELL", quantity=2))
    assert snapshot.position_quantity == -8
    assert snapshot.broker_ready is True
    assert snapshot.projected_trade_loss == 25.0
    assert snapshot.broker_snapshot_fingerprint


def test_snapshot_rejects_blocked_broker(tmp_path):
    p = provider(tmp_path, account={"status": "BLOCKED"})
    snapshot = p(request())
    assert snapshot.broker_ready is False


def test_snapshot_fails_closed_without_valid_entry_stop(tmp_path):
    p = provider(tmp_path)
    with pytest.raises(RuntimeError, match="entry price"):
        p(BrokerOrderRequest(client_order_id="risk-runtime-2", symbol="NIFTY", side="BUY", quantity=5))


def test_snapshot_rejects_stale_broker_snapshot(tmp_path):
    import time
    stale = BrokerSnapshot(orders=[], positions=[], fetched_at=time.time() - 10)
    p = provider(tmp_path, snapshot=stale, max_age=2)
    with pytest.raises(RuntimeError, match="stale"):
        p(request())


def test_snapshot_rejects_future_broker_snapshot(tmp_path):
    import time
    future = BrokerSnapshot(orders=[], positions=[], fetched_at=time.time() + 10)
    p = provider(tmp_path, snapshot=future, max_age=2)
    with pytest.raises(RuntimeError, match="stale"):
        p(request())


def test_snapshot_rejects_invalid_freshness_configuration(tmp_path):
    p = provider(tmp_path, max_age=0)
    with pytest.raises(RuntimeError, match="freshness configuration"):
        p(request())


def test_snapshot_fingerprint_changes_when_position_changes():
    first = BrokerSnapshot(orders=[], positions=[{"symbol": "NIFTY", "quantity": 5}])
    second = BrokerSnapshot(orders=[], positions=[{"symbol": "NIFTY", "quantity": 6}])
    assert first.fingerprint() != second.fingerprint()


def test_snapshot_fingerprint_is_order_independent():
    first = BrokerSnapshot(orders=[{"order_id": "2"}, {"order_id": "1"}], positions=[])
    second = BrokerSnapshot(orders=[{"order_id": "1"}, {"order_id": "2"}], positions=[])
    assert first.fingerprint() == second.fingerprint()


def test_service_uses_request_scoped_broker_position_for_risk(tmp_path):
    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = Broker(positions=[{"symbol": "NIFTY", "quantity": 18}], account={"status": "READY"})
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    recovery = StartupRecoveryCoordinator()
    recovery.begin()
    recovery.state = recovery.state.READY
    gate = PreTradeRiskGate(RiskLimits(10, 20, 1000, 200))
    snapshot_provider = RuntimeRiskSnapshotProvider(router, lifecycle)
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "state.json")), recovery=recovery, risk_gate=gate, risk_snapshot_provider=snapshot_provider)
    result = service.submit(request(quantity=5))
    assert result.status == "REJECTED"
    assert result.message == "RISK_MAX_POSITION_QUANTITY"


def test_service_blocks_when_broker_state_changes_after_reservation(tmp_path):
    class ChangingBroker(Broker):
        def __init__(self):
            super().__init__(account={"status": "READY"})
            self.snapshots = [
                BrokerSnapshot(orders=[], positions=[{"symbol": "NIFTY", "quantity": 0}]),
                BrokerSnapshot(orders=[], positions=[{"symbol": "NIFTY", "quantity": 8}]),
            ]
            self.submit_calls = 0

        def get_snapshot(self):
            return self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]

        def submit_order(self, request):
            self.submit_calls += 1
            raise AssertionError("submission must be blocked after broker state change")

    safety = SafetyStateStore(str(tmp_path / "safety.json"))
    safety.clear()
    broker = ChangingBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=safety)
    lifecycle = OrderLifecycle()
    recovery = StartupRecoveryCoordinator()
    recovery.begin()
    recovery.state = recovery.state.READY
    gate = PreTradeRiskGate(RiskLimits(10, 20, 1000, 200))
    snapshot_provider = RuntimeRiskSnapshotProvider(router, lifecycle)
    service = OrderExecutionService(router, lifecycle, ExecutionStateStore(str(tmp_path / "state.json")), recovery=recovery, risk_gate=gate, risk_snapshot_provider=snapshot_provider)
    result = service.submit(request(quantity=5))
    assert result.status == "REJECTED"
    assert result.message == "RISK_BROKER_SNAPSHOT_CHANGED"
    assert broker.submit_calls == 0
    assert gate.reservations.get("risk-runtime-1") is None
