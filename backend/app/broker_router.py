from __future__ import annotations

from dataclasses import dataclass
from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_snapshot import BrokerSnapshot
from app.trading_gate import TradingGate


@dataclass(frozen=True)
class BrokerRoute:
    name: str
    adapter: BrokerAdapter
    enabled: bool = True


class BrokerRouter:
    def __init__(self, routes: list[BrokerRoute], default_route: str, trading_gate: TradingGate | None = None):
        self.routes = {r.name: r for r in routes}
        self.default_route = default_route
        self.trading_gate = trading_gate
        if default_route not in self.routes:
            raise ValueError("default broker route is not configured")

    def get(self, name: str | None = None) -> BrokerRoute:
        route = self.routes.get(name or self.default_route)
        if route is None or not route.enabled:
            raise ValueError("broker route unavailable")
        return route

    def submit(self, request: BrokerOrderRequest, route: str | None = None, trading_halted: bool = False) -> BrokerOrderUpdate:
        if self.trading_gate is not None:
            self.trading_gate.require_ready(trading_halted)
        return self.get(route).adapter.submit_order(request)

    def cancel(self, order_id: str, route: str | None = None) -> BrokerOrderUpdate:
        return self.get(route).adapter.cancel_order(order_id)

    def get_order(self, order_id: str, route: str | None = None) -> dict:
        return self.get(route).adapter.get_order(order_id)

    def get_orders(self, route: str | None = None) -> list[dict]:
        adapter = self.get(route).adapter
        get_orders = getattr(adapter, "get_orders", None)
        if get_orders is None:
            raise NotImplementedError("broker does not support order snapshots")
        return get_orders()

    def get_positions(self, route: str | None = None) -> list[dict]:
        return self.get(route).adapter.get_positions()

    def get_account(self, route: str | None = None) -> dict:
        return self.get(route).adapter.get_account()

    def get_snapshot(self, route: str | None = None) -> BrokerSnapshot:
        adapter = self.get(route).adapter
        get_snapshot = getattr(adapter, "get_snapshot", None)
        if get_snapshot is not None:
            return get_snapshot()
        return BrokerSnapshot(
            orders=self.get_orders(route),
            positions=self.get_positions(route),
        )
