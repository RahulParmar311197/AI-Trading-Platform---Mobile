from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float | None
    multiplier: float = 1.0


@dataclass(frozen=True)
class BrokerOpenOrder:
    order_id: str
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float | None
    multiplier: float = 1.0


@dataclass(frozen=True)
class BrokerPortfolioSnapshot:
    broker: str
    captured_at: datetime
    positions: tuple[BrokerPosition, ...]
    open_orders: tuple[BrokerOpenOrder, ...]
    data_complete: bool
    error: str | None = None

    @classmethod
    def from_data(
        cls,
        broker: str,
        positions: Iterable[BrokerPosition],
        open_orders: Iterable[BrokerOpenOrder],
        captured_at: datetime,
        data_complete: bool = True,
        error: str | None = None,
    ) -> "BrokerPortfolioSnapshot":
        if not broker.strip():
            raise ValueError("broker is required")
        return cls(
            broker=broker.strip().lower(),
            captured_at=captured_at,
            positions=tuple(positions),
            open_orders=tuple(open_orders),
            data_complete=data_complete,
            error=error,
        )
