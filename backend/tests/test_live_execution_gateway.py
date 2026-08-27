import pytest

from app.live_execution_gateway import ExecutionMode, ExecutionPolicy, ExecutionSafetyError, LiveExecutionGateway
from app.order_intent import OrderIntent


class FakeExecutor:
    def __init__(self):
        self.orders = []

    def execute(self, order):
        self.orders.append(order)
        return {"status": "accepted"}


def make_order():
    return OrderIntent("NIFTY", "BUY", 100.0, 99.0, 102.0, 1, 1.0, "test", 0.8)


def test_paper_mode_delegates():
    executor = FakeExecutor()
    result = LiveExecutionGateway(executor).execute(make_order())
    assert result["status"] == "accepted"
    assert len(executor.orders) == 1


def test_live_mode_requires_explicit_enablement():
    with pytest.raises(ExecutionSafetyError, match="disabled"):
        LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(mode=ExecutionMode.LIVE)).execute(make_order())


def test_kill_switch_blocks_every_mode():
    with pytest.raises(ExecutionSafetyError, match="kill switch"):
        LiveExecutionGateway(FakeExecutor(), ExecutionPolicy(kill_switch=True)).execute(make_order())
