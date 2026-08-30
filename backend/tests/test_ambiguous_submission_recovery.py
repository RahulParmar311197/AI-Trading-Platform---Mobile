from __future__ import annotations

import pytest

from app.broker_adapter import BrokerOrderRequest
from app.live_execution_gateway import ExecutionSafetyError, LiveExecutionGateway
from app.broker_order_lifecycle import OrderStatus


class TimeoutWithRecoveryExecutor:
    def __init__(self, recovered):
        self.recovered = recovered
        self.submit_calls = 0
        self.lookup_calls = 0

    def execute(self, order):
        self.submit_calls += 1
        raise TimeoutError("transport timeout after broker submission")

    def find_order_by_client_id(self, client_order_id):
        self.lookup_calls += 1
        assert client_order_id == "client-1"
        return self.recovered


class TimeoutWithoutRecoveryExecutor:
    def __init__(self):
        self.submit_calls = 0

    def execute(self, order):
        self.submit_calls += 1
        raise TimeoutError("transport timeout")


def request(**overrides):
    values = dict(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        price=100,
        stop=99,
        target=102,
        broker_account_id="acct-1",
        broker_route="paper-route",
        broker_route_generation="route-gen-1",
    )
    values.update(overrides)
    return BrokerOrderRequest(**values)


def test_timeout_recovers_existing_broker_order_by_client_id_without_resubmit():
    executor = TimeoutWithRecoveryExecutor(
        {
            "order_id": "broker-1",
            "status": "FILLED",
            "client_order_id": "client-1",
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 1,
            "filled_quantity": 1,
            "average_price": 100,
            "broker_account_id": "acct-1",
            "broker_route": "paper-route",
            "broker_route_generation": "route-gen-1",
        }
    )
    gateway = LiveExecutionGateway(executor)

    tracked = gateway.execute_request(request())

    assert executor.submit_calls == 1
    assert executor.lookup_calls == 1
    assert tracked.lifecycle.status is OrderStatus.FILLED
    assert tracked.lifecycle.filled_quantity == 1


def test_timeout_with_no_authoritative_lookup_fails_closed_without_retry():
    executor = TimeoutWithoutRecoveryExecutor()
    gateway = LiveExecutionGateway(executor)

    with pytest.raises(ExecutionSafetyError, match="submission outcome is unknown"):
        gateway.execute_request(request())

    assert executor.submit_calls == 1


def test_recovery_rejects_broker_order_from_wrong_account_without_resubmit():
    executor = TimeoutWithRecoveryExecutor(
        {
            "order_id": "broker-2",
            "status": "FILLED",
            "client_order_id": "client-1",
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 1,
            "filled_quantity": 1,
            "average_price": 100,
            "broker_account_id": "acct-2",
            "broker_route": "paper-route",
            "broker_route_generation": "route-gen-1",
        }
    )
    gateway = LiveExecutionGateway(executor)

    with pytest.raises(ExecutionSafetyError, match="submission outcome is unknown"):
        gateway.execute_request(request())

    assert executor.submit_calls == 1
    assert executor.lookup_calls == 1
