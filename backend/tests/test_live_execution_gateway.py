import math

import pytest

from app.live_execution_gateway import (
    ExecutionMode,
    ExecutionPolicy,
    ExecutionSafetyError,
    LiveExecutionGateway,
)
from app.order_intent import OrderIntent


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


def live_gateway(executor=None):
    executor = executor or FakeExecutor()
    positions = []
    return LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=FakePositionReader(positions),
        local_positions_reader=lambda: positions,
    )


def test_paper_mode_delegates():
    executor = FakeExecutor()
    result = LiveExecutionGateway(executor).execute(make_order())
    assert result.result["status"] == "accepted"
    assert len(executor.orders) == 1


def test_live_mode_requires_explicit_enablement():
    with pytest.raises(ExecutionSafetyError, match="disabled"):
        LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(mode=ExecutionMode.LIVE)).execute(make_order())


def test_kill_switch_blocks_every_mode():
    with pytest.raises(ExecutionSafetyError, match="kill switch"):
        LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(kill_switch=True)).execute(make_order())


def test_invalid_nan_order_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "BUY", math.nan, 99.0, 102.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(executor).execute(order)
    assert executor.orders == []


def test_invalid_side_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "HOLD", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(executor).execute(order)
    assert executor.orders == []


def test_invalid_confidence_is_blocked_before_executor():
    executor = FakeExecutor()
    order = OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 1.5)
    with pytest.raises(ExecutionSafetyError, match="invalid order intent"):
        LiveExecutionGateway(executor).execute(order)
    assert executor.orders == []


def test_live_execution_requires_single_use_authorization():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    with pytest.raises(ExecutionSafetyError, match="single-use execution authorization"):
        gateway.execute(make_order())
    assert executor.orders == []


def test_live_authorization_is_consumed_after_one_execution():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    authorization = gateway.authorize(make_order())
    result = gateway.execute(make_order(), authorization)
    assert result.result["status"] == "accepted"
    assert len(executor.orders) == 1
    with pytest.raises(ExecutionSafetyError, match="already-consumed"):
        gateway.execute(make_order(), authorization)
    assert len(executor.orders) == 1


def test_live_authorization_is_bound_to_order():
    executor = FakeExecutor()
    gateway = live_gateway(executor)
    authorization = gateway.authorize(make_order())
    changed = OrderIntent("NIFTY", "BUY", 101.0, 99.0, 103.0, 1, 1.0, "test", 0.8)
    with pytest.raises(ExecutionSafetyError, match="different order"):
        gateway.execute(changed, authorization)
    assert executor.orders == []


def test_live_authorization_requires_current_reconciliation():
    executor = FakeExecutor()
    gateway = LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
        position_reader=FakePositionReader([{"symbol": "NIFTY", "quantity": 1}]),
        local_positions_reader=lambda: [],
    )
    with pytest.raises(ExecutionSafetyError, match="reconciliation failed"):
        gateway.authorize(make_order())
    assert executor.orders == []


def test_live_authorization_rejects_invalid_ttl():
    gateway = LiveExecutionGateway(
        FakeExecutor(),
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True, authorization_ttl_seconds=0),
        position_reader=FakePositionReader(),
        local_positions_reader=lambda: [],
    )
    with pytest.raises(ExecutionSafetyError, match="TTL"):
        gateway.authorize(make_order())
