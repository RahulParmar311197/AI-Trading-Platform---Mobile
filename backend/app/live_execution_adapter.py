from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class LiveExecutionConfig:
    enabled: bool = False
    broker_name: str = ""
    account_id: str = ""


class BrokerExecution(Protocol):
    def submit(self, order: dict) -> dict: ...
    def cancel(self, order_id: str) -> bool: ...
    def positions(self) -> list[dict]: ...


class LiveExecutionAdapter:
    """Safety boundary for real broker execution; disabled unless explicitly enabled."""

    def __init__(self, broker: BrokerExecution | None = None, config: LiveExecutionConfig | None = None):
        self.broker = broker
        self.config = config or LiveExecutionConfig()

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled and self.broker is not None and self.config.broker_name and self.config.account_id)

    def submit(self, order: dict) -> dict:
        if not self.enabled:
            raise RuntimeError("live execution is disabled or incompletely configured")
        if not order.get("symbol") or order.get("quantity", 0) <= 0:
            raise ValueError("invalid live order")
        return self.broker.submit(order)

    def cancel(self, order_id: str) -> bool:
        if not self.enabled:
            raise RuntimeError("live execution is disabled")
        if not order_id:
            raise ValueError("order_id is required")
        return self.broker.cancel(order_id)

    def positions(self) -> list[dict]:
        if not self.enabled:
            raise RuntimeError("live execution is disabled")
        return self.broker.positions()
