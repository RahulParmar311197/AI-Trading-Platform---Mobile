from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.broker_contracts import BrokerExecutionError


@dataclass(frozen=True)
class BrokerConfig:
    name: str
    enabled: bool = False
    account_id: str = ""
    environment: str = "paper"


class BrokerRegistry:
    """Maps broker names to adapters without coupling strategy code to vendors."""

    def __init__(self):
        self._factories: dict[str, Callable[[BrokerConfig], object]] = {}

    def register(self, name: str, factory: Callable[[BrokerConfig], object]) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("broker name is required")
        if key in self._factories:
            raise ValueError(f"broker already registered: {name}")
        self._factories[key] = factory

    def create(self, config: BrokerConfig) -> object:
        key = config.name.strip().lower()
        if not config.enabled:
            raise BrokerExecutionError(f"broker '{config.name}' is disabled")
        if config.environment not in {"paper", "live"}:
            raise ValueError("environment must be paper or live")
        if not config.account_id:
            raise ValueError("account_id is required")
        factory = self._factories.get(key)
        if factory is None:
            raise BrokerExecutionError(f"no adapter registered for broker '{config.name}'")
        return factory(config)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
