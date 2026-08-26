from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Sequence


@dataclass(frozen=True)
class MarketTick:
    """Normalized broker-independent market tick."""

    symbol: str
    timestamp: datetime
    price: float
    volume: float = 0.0


class MarketDataAdapter(ABC):
    """Broker-neutral interface for live market data.

    Execution/account operations intentionally remain on BrokerAdapter.
    Implementations own only market-data connection and subscription state.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish the market-data session."""

    @abstractmethod
    async def subscribe(self, symbols: Sequence[str]) -> None:
        """Subscribe to normalized instrument symbols."""

    @abstractmethod
    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        """Remove market-data subscriptions."""

    @abstractmethod
    def stream_ticks(self) -> AsyncIterator[MarketTick]:
        """Yield normalized ticks until the stream terminates."""

    @abstractmethod
    async def close(self) -> None:
        """Close the market-data session and release resources."""
