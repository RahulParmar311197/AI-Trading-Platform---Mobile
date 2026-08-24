"""Legacy broker compatibility API.

Production execution MUST use app.broker_router.BrokerRouter and the concrete
adapters selected by app.broker_factory. This module remains only for older
imports and paper-mode compatibility; its Dhan/Upstox classes intentionally
cannot perform live execution.
"""

from abc import ABC, abstractmethod
from app.schemas import OrderRequest


class Broker(ABC):
    """Deprecated compatibility interface; not a live execution boundary."""

    @abstractmethod
    async def get_account(self): ...

    @abstractmethod
    async def get_positions(self): ...

    @abstractmethod
    async def get_orders(self): ...

    @abstractmethod
    async def place_order(self, order: OrderRequest): ...

    @abstractmethod
    async def cancel_order(self, order_id: str): ...


class PaperBroker(Broker):
    """Legacy paper-only broker kept for backwards compatibility."""

    def __init__(self):
        self.orders = []

    async def get_account(self):
        return {"mode": "PAPER", "balance": 100000}

    async def get_positions(self):
        return []

    async def get_orders(self):
        return self.orders

    async def place_order(self, order):
        record = {"id": str(len(self.orders) + 1), "status": "FILLED", **order.model_dump()}
        self.orders.append(record)
        return record

    async def cancel_order(self, order_id):
        return {"id": order_id, "status": "CANCELLED"}


class DhanBroker(Broker):
    """Deprecated stub: live Dhan execution belongs to DhanAdapter + BrokerRouter."""

    async def get_account(self):
        raise NotImplementedError("Use app.dhan_adapter.DhanAdapter through BrokerRouter")

    async def get_positions(self):
        raise NotImplementedError("Use app.dhan_adapter.DhanAdapter through BrokerRouter")

    async def get_orders(self):
        raise NotImplementedError("Use app.dhan_adapter.DhanAdapter through BrokerRouter")

    async def place_order(self, order):
        raise NotImplementedError("Live execution through legacy DhanBroker is disabled")

    async def cancel_order(self, order_id):
        raise NotImplementedError("Live execution through legacy DhanBroker is disabled")


class UpstoxBroker(DhanBroker):
    """Deprecated stub: live Upstox execution belongs to UpstoxAdapter + BrokerRouter."""
    pass
