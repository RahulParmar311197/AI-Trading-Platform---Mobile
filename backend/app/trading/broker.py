from abc import ABC, abstractmethod
from app.schemas import OrderRequest

class Broker(ABC):
    @abstractmethod
    async def get_account(self): ...
    @abstractmethod
    async def get_positions(self): ...
    @abstractmethod
    async def get_orders(self): ...
    @abstractmethod
    async def place_order(self, order:OrderRequest): ...
    @abstractmethod
    async def cancel_order(self, order_id:str): ...

class PaperBroker(Broker):
    def __init__(self): self.orders=[]
    async def get_account(self): return {"mode":"PAPER","balance":100000}
    async def get_positions(self): return []
    async def get_orders(self): return self.orders
    async def place_order(self, order):
        record={"id":str(len(self.orders)+1),"status":"FILLED",**order.model_dump()}; self.orders.append(record); return record
    async def cancel_order(self, order_id): return {"id":order_id,"status":"CANCELLED"}

class DhanBroker(Broker):
    async def get_account(self): raise NotImplementedError("Configure current Dhan API adapter before live trading")
    async def get_positions(self): raise NotImplementedError
    async def get_orders(self): raise NotImplementedError
    async def place_order(self, order): raise NotImplementedError
    async def cancel_order(self, order_id): raise NotImplementedError

class UpstoxBroker(DhanBroker):
    pass
