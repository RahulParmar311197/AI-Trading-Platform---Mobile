from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InternalTradingState:
    positions: dict[str, float]
    open_order_ids: frozenset[str]


class InternalTradingStateProvider(ABC):
    """Source of the execution engine's current internal state."""

    @abstractmethod
    def get_state(self) -> InternalTradingState:
        raise NotImplementedError


class InMemoryTradingStateProvider(InternalTradingStateProvider):
    """Deterministic state provider for paper trading and integration tests."""

    def __init__(self) -> None:
        self._positions: dict[str, float] = {}
        self._open_order_ids: frozenset[str] = frozenset()

    def set_state(self, *, positions: dict[str, float], open_order_ids: set[str] | frozenset[str]) -> None:
        self._positions = {str(k).upper(): float(v) for k, v in positions.items()}
        self._open_order_ids = frozenset(open_order_ids)

    def get_state(self) -> InternalTradingState:
        return InternalTradingState(dict(self._positions), self._open_order_ids)
