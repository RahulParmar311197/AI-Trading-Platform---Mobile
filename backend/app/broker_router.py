from __future__ import annotations
from dataclasses import dataclass
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate

@dataclass(frozen=True)
class BrokerRoute:
    name:str
    adapter:BrokerAdapter
    enabled:bool=True

class BrokerRouter:
    def __init__(self, routes:list[BrokerRoute], default_route:str):
        self.routes={r.name:r for r in routes}; self.default_route=default_route
        if default_route not in self.routes: raise ValueError('default broker route is not configured')

    def get(self,name:str|None=None)->BrokerRoute:
        route=self.routes.get(name or self.default_route)
        if route is None or not route.enabled: raise ValueError('broker route unavailable')
        return route

    def submit(self,request:BrokerOrderRequest,route:str|None=None)->BrokerOrderUpdate:
        return self.get(route).adapter.submit_order(request)

    def cancel(self,order_id:str,route:str|None=None)->BrokerOrderUpdate:
        return self.get(route).adapter.cancel_order(order_id)
