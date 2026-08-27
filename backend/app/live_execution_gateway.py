from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.broker_order_lifecycle import OrderLifecycle, OrderLifecycleEvent, OrderStatus
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


@dataclass(frozen=True)
class TrackedExecution:
    result: object
    lifecycle: OrderLifecycle


class LiveExecutionGateway:
    """Single safety boundary between approved trade intents and broker execution."""

    def __init__(self, executor: BrokerExecutor, policy: ExecutionPolicy | None = None) -> None:
        self.executor = executor
        self.policy = policy or ExecutionPolicy()

    def execute(self, order: OrderIntent) -> TrackedExecution:
        if self.policy.kill_switch:
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is ExecutionMode.LIVE and not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")
        try:
            safe_order = order.normalized()
            safe_order.validate()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExecutionSafetyError(f"execution blocked: invalid order intent: {exc}") from exc

        lifecycle = OrderLifecycle()
        lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.ACCEPTED, timestamp=_now()))
        try:
            result = self.executor.execute(safe_order)
        except Exception as exc:
            lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.REJECTED, timestamp=_now(), reason=str(exc)))
            raise
        return TrackedExecution(result=result, lifecycle=lifecycle)


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
