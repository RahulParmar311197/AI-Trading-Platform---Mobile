from abc import ABC, abstractmethod
from typing import Any

class BrokerAdapter(ABC):
    """Provider-neutral broker contract used by execution/risk layers."""
    @abstractmethod
    def get_quote(self, symbol: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def place_order(self, order: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...
