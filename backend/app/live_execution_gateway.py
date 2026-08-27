from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.order_intent import OrderIntent


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ExecutionSafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: ExecutionMode = ExecutionMode.PAPER
    live_trading_enabled: bool = False
    kill_switch: bool = False


class BrokerExecutor(Protocol):
    def execute(self, order: OrderIntent): ...


class LiveExecutionGateway:
    """Single safety boundary between approved trade intents and broker execution."""

    def __init__(self, executor: BrokerExecutor, policy: ExecutionPolicy | None = None) -> None:
        self.executor = executor
        self.policy = policy or ExecutionPolicy()

    def execute(self, order: OrderIntent):
        if self.policy.kill_switch:
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is ExecutionMode.LIVE and not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")
        return self.executor.execute(order)
