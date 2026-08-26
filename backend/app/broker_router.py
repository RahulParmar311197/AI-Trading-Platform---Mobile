from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from threading import Lock, RLock
from typing import Iterator

from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_snapshot import BrokerSnapshot
from app.safety_state import SafetyStateStore
from app.trading_gate import TradingGate


@dataclass(frozen=True)
class BrokerRoute:
    name: str
    adapter: BrokerAdapter
    enabled: bool = True
    broker_account_id: int | None = None
    generation: str | None = None


class BrokerRouter:
    def __init__(self, routes: list[BrokerRoute], default_route: str, safety_store: SafetyStateStore | None = None, trading_gate: TradingGate | None = None):
        self.routes = {r.name: r for r in routes}
        self.default_route = default_route
        self.safety_store = safety_store
        self.trading_gate = trading_gate or TradingGate()
        self._submission_lock = Lock()
        self._submission_claims = set()
        self._route_lifecycle_lock = RLock()
        if default_route not in self.routes:
            raise ValueError("default broker route is not configured")

    @contextmanager
    def route_lifecycle_lock(self) -> Iterator[None]:
        """Serialize account-route replacement with broker operations."""
        with self._route_lifecycle_lock:
            yield

    def get(self, name=None):
        route = self.routes.get(name or self.default_route)
        if route is None or not route.enabled:
            raise ValueError("broker route unavailable")
        return route

    def _require_execution_ready(self):
        halted = self.safety_store.load().trading_halted if self.safety_store else True
        self.trading_gate.require_ready(halted)

    def _require_account_binding(self, request: BrokerOrderRequest, route: BrokerRoute) -> None:
        if request.broker_account_id is None:
            return
        if route.broker_account_id is None:
            raise RuntimeError("broker route is not bound to a broker account")
        if int(route.broker_account_id) != int(request.broker_account_id):
            raise RuntimeError("broker account does not match broker route")
        if request.broker_route_generation is None:
            raise RuntimeError("broker account route generation is required")
        if route.generation is None or str(route.generation) != str(request.broker_route_generation):
            raise RuntimeError("broker account route generation is stale")

    def submit(self, request: BrokerOrderRequest, route=None):
        with self._route_lifecycle_lock:
            self._require_execution_ready()
            selected_route = route or request.broker_route or self.default_route
            selected = self.get(selected_route)
            self._require_account_binding(request, selected)
            key = (selected_route, str(request.client_order_id))
            with self._submission_lock:
                if key in self._submission_claims:
                    existing = self.find_order_by_client_id(request.client_order_id, selected_route)
                    if existing is not None:
                        return BrokerOrderUpdate(order_id=str(existing.get("order_id", existing.get("broker_order_id"))), status=str(existing.get("status", "NEW")), client_order_id=existing.get("client_order_id"), symbol=existing.get("symbol"), side=existing.get("side"), quantity=existing.get("quantity"), filled_quantity=existing.get("filled_quantity", existing.get("filledQty", 0)), price=existing.get("price"), average_price=existing.get("average_price", existing.get("averagePrice")), message="BROKER_CLIENT_ID_REPLAY")
                    raise RuntimeError("submission already in progress for client_order_id")
                existing = self.find_order_by_client_id(request.client_order_id, selected_route)
                if existing is not None:
                    return BrokerOrderUpdate(order_id=str(existing.get("order_id", existing.get("broker_order_id"))), status=str(existing.get("status", "NEW")), client_order_id=existing.get("client_order_id"), symbol=existing.get("symbol"), side=existing.get("side"), quantity=existing.get("quantity"), filled_quantity=existing.get("filled_quantity", existing.get("filledQty", 0)), price=existing.get("price"), average_price=existing.get("average_price", existing.get("averagePrice")), message="BROKER_CLIENT_ID_REPLAY")
                self._submission_claims.add(key)
            try:
                return selected.adapter.submit_order(request)
            finally:
                with self._submission_lock:
                    self._submission_claims.discard(key)

    def cancel(self, order_id, route=None):
        with self._route_lifecycle_lock:
            self._require_execution_ready()
            if not str(order_id).strip():
                raise ValueError("order_id is required")
            return self.get(route).adapter.cancel_order(order_id)

    def get_order(self, order_id, route=None):
        with self._route_lifecycle_lock:
            return self.get(route).adapter.get_order(order_id)

    def get_orders(self, route=None):
        with self._route_lifecycle_lock:
            get_orders = getattr(self.get(route).adapter, "get_orders", None)
            if get_orders is None:
                raise NotImplementedError("broker does not support order snapshots")
            return get_orders()

    def find_order_by_client_id(self, client_order_id, route=None):
        with self._route_lifecycle_lock:
            selected = self.get(route)
            get_orders = getattr(selected.adapter, "get_orders", None)
            if get_orders is not None:
                matches = [dict(order) for order in get_orders() if str(order.get("client_order_id", "")) == str(client_order_id)]
                if len(matches) > 1:
                    raise RuntimeError(f"ambiguous broker order identity for client_order_id: {client_order_id}")
                return matches[0] if matches else None
            return selected.adapter.find_order_by_client_id(client_order_id)

    def get_positions(self, route=None):
        with self._route_lifecycle_lock:
            return self.get(route).adapter.get_positions()

    def get_account(self, route=None):
        with self._route_lifecycle_lock:
            return self.get(route).adapter.get_account()

    def get_snapshot(self, route=None):
        with self._route_lifecycle_lock:
            selected = self.get(route)
            adapter = selected.adapter
            get_snapshot = getattr(adapter, "get_snapshot", None)
            snapshot = get_snapshot() if get_snapshot is not None else BrokerSnapshot(orders=self.get_orders(selected.name), positions=self.get_positions(selected.name))
            if not isinstance(snapshot, BrokerSnapshot):
                snapshot = BrokerSnapshot(orders=list(snapshot.orders), positions=list(snapshot.positions), fetched_at=float(snapshot.fetched_at))
            return replace(snapshot, broker_route=selected.name, broker_account_id=selected.broker_account_id)
