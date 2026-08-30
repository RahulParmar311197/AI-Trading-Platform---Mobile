from __future__ import annotations

import pytest

from app.broker_adapter import BrokerOrderRequest
from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway, _order_intent_from_request


class RequestAwareExecutor:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.legacy_calls = 0

    def submit_order(self, request):
        self.requests.append(request)
        return self.response

    def execute(self, order):
        self.legacy_calls += 1
        raise AssertionError("legacy execute() must not be used when a broker request is available")


class LegacyOnlyExecutor:
    def __init__(self):
        self.calls = 0

    def execute(self, order):
        self.calls += 1
        return {"order_id": "broker-1", "status": "NEW"}


def request():
    return BrokerOrderRequest(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        price=100,
        stop=99,
        target=102,
        broker_account_id="acct-1",
        broker_route="upstox",
        broker_route_generation="gen-1",
    )


def test_request_aware_submission_passes_original_broker_request_to_executor():
    executor = RequestAwareExecutor(
        {
            "order_id": "broker-1",
            "status": "NEW",
            "client_order_id": "client-1",
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 1,
            "filled_quantity": 0,
            "broker_account_id": "acct-1",
            "broker_route": "upstox",
            "broker_route_generation": "gen-1",
        }
    )
    gateway = LiveExecutionGateway(executor, ExecutionPolicy(mode=ExecutionMode.PAPER))

    tracked = gateway.execute_request(request())

    assert len(executor.requests) == 1
    assert executor.requests[0].client_order_id == "client-1"
    assert executor.requests[0].broker_account_id == "acct-1"
    assert executor.requests[0].broker_route == "upstox"
    assert executor.requests[0].broker_route_generation == "gen-1"
    assert executor.legacy_calls == 0
    assert tracked.result["order_id"] == "broker-1"


def test_live_submission_rejects_legacy_executor_without_request_aware_capability():
    executor = LegacyOnlyExecutor()
    gateway = LiveExecutionGateway(
        executor,
        ExecutionPolicy(mode=ExecutionMode.LIVE, live_trading_enabled=True),
    )

    with pytest.raises(ExecutionSafetyError, match="request-aware submit_order"):
        gateway._submit(_order_intent_from_request(request()), request())

    assert executor.calls == 0
