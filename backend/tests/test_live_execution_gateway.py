from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import pytest

from app.broker_adapter import BrokerOrderUpdate
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway
from app.order_intent import OrderIntent
from app.broker_order_lifecycle import InvalidOrderTransition, OrderStatus

SECRET = b"t" * 32

class FakeExecutor:
    def __init__(self): self.orders = []
    def execute(self, order): self.orders.append(order); return {"status": "accepted"}

class UpdateExecutor:
    def __init__(self, update): self.update = update; self.orders = []
    def execute(self, order): self.orders.append(order); return self.update

class FakePositionReader:
    def __init__(self, positions=None): self.positions = positions or []
    def get_positions(self): return self.positions

def make_order(): return OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)

def make_context(generation=7, fingerprint="snapshot", observed_at=None, attested=True):
    observed_at = observed_at or datetime.now(timezone.utc)
    base = BrokerExecutionContext("acct-1", "paper-route", "route-gen-1", generation, fingerprint, observed_at)
    signature = BrokerContextAttestor(SECRET).sign(account_id=base.account_id, broker_route=base.broker_route, route_generation=base.route_generation, generation=base.generation, snapshot_fingerprint=base.snapshot_fingerprint, observed_at=base.observed_at) if attested else ""
    return BrokerExecutionContext(base.account_id, base.broker_route, base.route_generation, base.generation, base.snapshot_fingerprint, base.observed_at, signature)

def live_gateway(executor=None, store=None, policy=None, positions=None, local=None):
    positions = positions or []
    return LiveExecutionGateway(executor or FakeExecutor(), policy or ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True), position_reader=FakePositionReader(positions), local_positions_reader=lambda: positions if local is None else local, authorization_store=store or ExecutionAuthorizationStore(":memory:"), context_attestor=BrokerContextAttestor(SECRET))

def test_paper_mode_delegates():
    executor = FakeExecutor(); assert LiveExecutionGateway(executor, authorization_store=ExecutionAuthorizationStore(":memory:")).execute(make_order()).result["status"] == "accepted"

def test_paper_broker_update_reaches_terminal_lifecycle():
    executor = UpdateExecutor(BrokerOrderUpdate(order_id="b1", status="FILLED", client_order_id="c1", symbol="NIFTY", side="BUY", quantity=1, filled_quantity=1, average_price=100))
    gateway = LiveExecutionGateway(executor, authorization_store=ExecutionAuthorizationStore(":memory:"))
    tracked = gateway.execute(make_order())
    assert tracked.lifecycle.status is OrderStatus.FILLED
    assert tracked.lifecycle.filled_quantity == 1
    assert tracked.lifecycle.average_price == 100
    assert tracked.lifecycle.events[-1].broker_order_id == "b1"

def test_broker_partial_fill_is_projected_into_lifecycle():
    executor = UpdateExecutor(BrokerOrderUpdate(order_id="b2", status="PARTIALLY_FILLED", client_order_id="c2", symbol="NIFTY", side="BUY", quantity=1, filled_quantity=0.5, average_price=100))
    tracked = LiveExecutionGateway(executor, authorization_store=ExecutionAuthorizationStore(":memory:")).execute(make_order())
    assert tracked.lifecycle.status is OrderStatus.PARTIALLY_FILLED
    assert tracked.lifecycle.filled_quantity == 0.5

def test_broker_rejection_is_terminal_lifecycle_state_without_duplicate_rejection_transition():
    executor = UpdateExecutor(BrokerOrderUpdate(order_id="b3", status="REJECTED", client_order_id="c3", symbol="NIFTY", side="BUY", quantity=1, filled_quantity=0, message="broker rejected"))
    tracked = LiveExecutionGateway(executor, authorization_store=ExecutionAuthorizationStore(":memory:")).execute(make_order())
    assert tracked.lifecycle.status is OrderStatus.REJECTED
    assert len(tracked.lifecycle.events) == 2
    assert tracked.lifecycle.events[-1].reason == "broker rejected"

def test_lifecycle_rejects_negative_and_non_finite_fills():
    lifecycle = __import__("app.broker_order_lifecycle", fromlist=["OrderLifecycle"]).OrderLifecycle(requested_quantity=1)
    lifecycle.apply(__import__("app.broker_order_lifecycle", fromlist=["OrderLifecycleEvent"]).OrderLifecycleEvent(OrderStatus.ACCEPTED, datetime.now(timezone.utc)))
    with pytest.raises(InvalidOrderTransition, match="finite and non-negative"):
        lifecycle.apply(__import__("app.broker_order_lifecycle", fromlist=["OrderLifecycleEvent"]).OrderLifecycleEvent(OrderStatus.PARTIALLY_FILLED, datetime.now(timezone.utc), filled_quantity=math.nan))

def test_lifecycle_rejects_fill_above_requested_quantity():
    lifecycle = __import__("app.broker_order_lifecycle", fromlist=["OrderLifecycle"]).OrderLifecycle(requested_quantity=1)
    lifecycle.apply(__import__("app.broker_order_lifecycle", fromlist=["OrderLifecycleEvent"]).OrderLifecycleEvent(OrderStatus.ACCEPTED, datetime.now(timezone.utc)))
    with pytest.raises(InvalidOrderTransition, match="cannot exceed"):
        lifecycle.apply(__import__("app.broker_order_lifecycle", fromlist=["OrderLifecycleEvent"]).OrderLifecycleEvent(OrderStatus.FILLED, datetime.now(timezone.utc), filled_quantity=2))

def test_lifecycle_rejects_out_of_order_timestamps():
    lifecycle = __import__("app.broker_order_lifecycle", fromlist=["OrderLifecycle"]).OrderLifecycle()
    now = datetime.now(timezone.utc)
    Event = __import__("app.broker_order_lifecycle", fromlist=["OrderLifecycleEvent"]).OrderLifecycleEvent
    lifecycle.apply(Event(OrderStatus.ACCEPTED, now))
    with pytest.raises(InvalidOrderTransition, match="timestamp"):
        lifecycle.apply(Event(OrderStatus.REJECTED, now - timedelta(seconds=1)))

def test_live_mode_requires_explicit_enablement():
    with pytest.raises(ExecutionSafetyError, match="disabled"): LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(mode=ExecutionMode.LIVE), authorization_store=ExecutionAuthorizationStore(":memory:")).execute(make_order())

def test_kill_switch_blocks_every_mode():
    with pytest.raises(ExecutionSafetyError, match="kill switch"): LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(kill_switch=True), authorization_store=ExecutionAuthorizationStore(":memory:")).execute(make_order())

def test_invalid_order_never_reaches_executor():
    executor = FakeExecutor(); order = OrderIntent("NIFTY", "BUY", math.nan, 99.0, 102.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"): LiveExecutionGateway(executor, authorization_store=ExecutionAuthorizationStore(":memory:")).execute(order)
    assert executor.orders == []

def test_live_authorization_requires_attested_context():
    gateway = live_gateway()
    with pytest.raises(ExecutionSafetyError, match="not coordinator-attested"): gateway.authorize(make_order(), make_context(attested=False))

def test_authorization_is_single_use_and_atomic():
    store = ExecutionAuthorizationStore(":memory:"); first = live_gateway(store=store); second_executor = FakeExecutor(); second = live_gateway(executor=second_executor, store=store); ctx = make_context(); auth = first.authorize(make_order(), ctx)
    first.execute(make_order(), auth, ctx)
    with pytest.raises(ExecutionSafetyError, match="already-consumed"): second.execute(make_order(), auth, ctx)
    assert len(second_executor.orders) == 0

def test_authorization_is_bound_to_order():
    gateway = live_gateway(); ctx = make_context(); auth = gateway.authorize(make_order(), ctx); changed = OrderIntent("NIFTY", "BUY", 101.0, 99.0, 103.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="different order"): gateway.execute(changed, auth, ctx)

def test_authorization_is_bound_to_context():
    gateway = live_gateway(); ctx = make_context(); auth = gateway.authorize(make_order(), ctx)
    with pytest.raises(ExecutionSafetyError, match="different broker context"): gateway.execute(make_order(), auth, make_context(fingerprint="different-snapshot"))

def test_reconciliation_mismatch_blocks_authorization():
    gateway = live_gateway(positions=[{"symbol": "NIFTY", "quantity": 1}], local=[{"symbol": "NIFTY", "quantity": 2}])
    with pytest.raises(ExecutionSafetyError, match="reconciliation failed"): gateway.authorize(make_order(), make_context())

def test_stale_context_blocks_authorization():
    gateway = live_gateway(policy=ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True, context_max_age_seconds=5))
    stale = make_context(observed_at=datetime.now(timezone.utc) - timedelta(seconds=6))
    with pytest.raises(ExecutionSafetyError, match="context is stale"): gateway.authorize(make_order(), stale)
