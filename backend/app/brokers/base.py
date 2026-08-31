from abc import ABC, abstractmethod
from typing import Any


class BrokerAdapter(ABC):
    """Provider-neutral broker contract used by execution/risk layers."""

    @abstractmethod
    def get_quote(self, symbol: str) -> dict[str, Any]: ...

    def get_historical_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        to_date: str,
        from_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return provider-native historical candle rows when supported.

        Brokers that do not expose historical candles fail explicitly rather than
        silently substituting quote data or a second market-data implementation.
        """
        raise NotImplementedError("historical candles are not supported by this broker")

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_orders(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_order(self, broker_order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_trades(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_trades_for_order(self, broker_order_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def place_order(self, order: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...
