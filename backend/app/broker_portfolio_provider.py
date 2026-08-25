from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.broker_portfolio_snapshot import BrokerOpenOrder, BrokerPortfolioSnapshot, BrokerPosition


class BrokerPortfolioProvider(ABC):
    """Provider contract for obtaining a canonical, point-in-time portfolio snapshot."""

    @abstractmethod
    def get_portfolio_snapshot(self) -> BrokerPortfolioSnapshot:
        raise NotImplementedError


class PaperBrokerPortfolioProvider(BrokerPortfolioProvider):
    """Deterministic in-memory provider for paper trading and integration tests."""

    def __init__(self, broker: str = "paper") -> None:
        self.broker = broker
        self._positions: tuple[BrokerPosition, ...] = ()
        self._open_orders: tuple[BrokerOpenOrder, ...] = ()
        self._data_complete = True
        self._error: str | None = None

    def set_snapshot(
        self,
        *,
        positions: tuple[BrokerPosition, ...] = (),
        open_orders: tuple[BrokerOpenOrder, ...] = (),
        data_complete: bool = True,
        error: str | None = None,
    ) -> None:
        self._positions = tuple(positions)
        self._open_orders = tuple(open_orders)
        self._data_complete = data_complete
        self._error = error

    def get_portfolio_snapshot(self) -> BrokerPortfolioSnapshot:
        return BrokerPortfolioSnapshot.from_data(
            self.broker,
            self._positions,
            self._open_orders,
            datetime.now(timezone.utc),
            data_complete=self._data_complete,
            error=self._error,
        )
