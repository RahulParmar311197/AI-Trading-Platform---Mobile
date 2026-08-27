import math
from datetime import datetime, timedelta, timezone

import pytest

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.live_execution_gateway import (
    ExecutionMode,
    ExecutionPolicy,
    ExecutionSafetyError,
    LiveExecutionGateway,
)
from app.order_intent import OrderIntent


SECRET = b"t" * 32


class FakeExecutor:
    def __init__(self):
        self.orders = []

    def execute(self, order):
        self.orders.append(order)
        return {"status": "accepted"}


class FakePositionReader:
    def __init__(self, positions=None):
        self.positions = positions or []

    def get_positions(self):
        return self.positions


def make_order():
    return OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)


def make_context(generation=7, fingerprint="snapshot", observed_at=None, attested=True):
    observed_at = observed_at or datetime.now(timezone.utc)
    base = BrokerExecutionContext(
        account_id="acct-1",
        broker_route="paper-route",
        route_generation="route-gen-1",
        generation=generation,
        snapshot_fingerprint=fingerprint,
        observed_at=observed_at,
    )
    attestation = BrokerContextAttestor(SECRET).sign(
        account_id=base.account_id,
        broker_route=base.broker_route,
        route_generation=base.route_generation,
        generation=base.generation,
        snapshot_fingerprint=base.snapshot_fingerprint,
        observed_at=base.observed_at,
    ) if attested else ""
    return BrokerExecutionContext(
        account_id=base.account_id,
        broker_route=base.broker_route,
        route_generation=base.route_generation,
        generation=base.generation,
        snapshot_fingerprint=base.snapshot_fingerprint,
        observed_at=base.observed_at,
        attestation=attestation,
    )


def live_gateway(executor=None, store=None, policy=None):
    executor = executor or FakeExecutor()
    positions = []
    return LiveExecutionGateway(
        executor,
        policy or ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=FakePositionReader(positions),
        local_positions_reader=lambda: positions,
        authorization_store=store or ExecutionAuthorizationStore(":memory:"),
        context_attestor=BrokerContextAttestor(SECRET),
    )


def test_paper_mode_delegates():
    executor = FakeExecutor()
    result = LiveExecutionGateway(
        executor,
        authorization_store=ExecutionAuthorizationStore(":memory:"),
    ).execute(make_order())
    assert result.result["status"] == "accepted"
    assert len(executor.orders) == 1


def test_live_mode_requires_explicit_enablement():
    with pytest.raises(ExecutionSafetyError, match="disabled"):
        LiveExecutionGateway(
            FakeExecutor(),
            ExecutionPolicy(mode=ExecutionMode.LIVE),
            authorization_store=ExecutionAuthorizationStore(":memory:"),
        ).execute(make_order())


def test_kill_switch_blocks_every_mode():
    with pytest.raises(ExecutionSafetyError, match="kill switch"):
        LiveExecutionGateway(
            FakeExecutor(),
            ExecutionPolicy(kill_switch=True),
            authorization_store=ExecutionAuthorizationStore(":memory:"),
        ).execute(make_order())


def test_invalid_nan_order_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "BUY", math.nan, 99.0, 102.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(
            executor,
            authorization_store=ExecutionAuthorizationStore(":memory:"),
        ).execute(order)
    assert executor.orders == []


def test_invalid_side_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "HOLD", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(
            executor,
            authorization_store=ExecutionAuthorizationStore(":memory:"),
        ).execute(order)
    assert executor.orders == []


def test_invalid_confidence_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 1.5)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(
            executor,
            authorization_store=ExecutionAuthorizationStore(":memory:"),
        ).execute(order)
    assert executor.orders == []


def test_live_execution_requires_single_use_authorization():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    with pytest.raises(ExecutionSafetyError, match="single-use execution authorization"):
        gateway.execute(make_order(), context=make_context())
    assert executor.orders == []


def test_live_authorization_rejects_unattested_context():
    gateway = live_gateway(FakeExecutor())
    with pytest.raises(ExecutionSafetyError, match="not coordinator-attested"):
        gateway.authorize(make_order(), make_context(attested=False))


def test_live_authorization_is_consumed_after_one_execution():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    context = make_context()
    authorization = gateway.authorize(make_order(), context)
    result = gateway.execute(make_order(), authorization, context)
    assert result.result["status"] == "accepted"
    assert len(executor.orders) == 1
    with pytest.raises(ExecutionSafetyError, match="already-consumed"):
        gateway.execute(make_order(), authorization, context)
    assert len(executor.orders) == 1


def test_live_authorization_survives_gateway_restart():
    store = ExecutionAuthorizationStore(":memory:")
    first = live_gateway(FakeExecutor(), store)
    context = make_context()
    authorization = first.authorize(make_order(), context)
    second_executor = FakeExecutor()
    second = live_gateway(second_executor, store)
    result = second.execute(make_order(), authorization, context)
    assert result.result["status"] == "accepted"
    assert len(second_executor.orders) == 1


def test_live_authorization_store_is_atomic_across_gateway_instances():
    store = ExecutionAuthorizationStore(":memory:")
    first_executor = FakeExecutor()
    second_executor = FakeExecutor()
    first = live_gateway(first_executor, store)
    second = live_gateway(second_executor, store)
    context = make_context()
    authorization = first.authorize(make_order(), context)
    first.execute(make_order(), authorization, context)
    with pytest.raises(ExecutionSafetyError, match="already-consumed"):
        second.execute(make_order(), authorization, context)
    assert len(first_executor.orders) == 1
    assert second_executor.orders == []


def test_live_authorization_is_bound_to_order():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    context = make_context()
    authorization = gateway.authorize(make_order(), context)
    changed = OrderIntent("NIFTY", "BUY", 101.0, 99.0, 103.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="different order"):
        gateway.execute(changed, authorization, context)
    assert executor.orders == []


def test_live_authorization_is_bound_to_broker_context():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    authorization = gateway.authorize(make_order(), make_context())
    changed_context = make_context(fingerprint="different-snapshot")
    with pytest.raises(ExecutionSafetyError, match="different broker context"):
        gateway.execute(make_order(), authorization, changed_context)
    assert executor.orders == []


def test_live_authorization_requires_context():
    gateway = live_gateway(FakeExecutor())
    with pytest.raises(ExecutionSafetyError, match="broker execution context"):
        gateway.authorize(make_order(), None)


def test_live_authorization_requires_current_reconciliation():
    executor = FakeExecutor()
    gateway = LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=FakePositionReader([{"symbol": "NIFTY", "quantity": 1}]),
        local_positions_reader=lambda: [],
        authorization_store=ExecutionAuthorizationStore(":memory:"),
        context_attestor=BrokerContextAttestor(SECRET),
    )
    with pytest.raises(ExecutionSafetyError, match="reconciliation failed"):
        gateway.authorize(make_order(), make_context())
    assert executor.orders == []


def test_live_authorization_rejects_stale_broker_context():
    gateway = live_gateway(
        FakeExecutor(),
        policy=ExecutionPolicy(
            mode=ExecutionMode.LIVE,
            live_trading_enabled=True,
            context_max_age_seconds=5,
        ),
    )
    stale = make_context(observed_at=datetime.now(timezone.utc) - timedelta(seconds=6))
    with pytest.raises(ExecutionSafetyError, match="context is stale"):
        gateway.authorize(make_order(), stale)


def test_live_authorization_rejects_non_positive_context_max_age():
    gateway = live_gateway(
        FakeExecutor(),
        policy=ExecutionPolicy(
            mode=ExecutionMode.LIVE,
            live_trading_enabled=True,
            context_max_age_seconds=0,
        ),
    )
    with pytest.raises(ExecutionSafetyError, match="context max age"):
        gateway.authorize(make_order(), make_context())


def test_live_authorization_rejects_invalid_ttl():
    gateway = LiveExecutionGateway(
        FakeExecutor(),
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True, authorization_ttl_seconds=0),
        position_reader=FakePositionReader(),
        local_positions_reader=lambda: [],
        authorization_store=ExecutionAuthorizationStore(":memory:"),
        context_attestor=BrokerContextAttestor(SECRET),
    )
    with pytest.raises(ExecutionSafetyError, match="TTL"):
        gateway.authorize(make_order(), make_context())
