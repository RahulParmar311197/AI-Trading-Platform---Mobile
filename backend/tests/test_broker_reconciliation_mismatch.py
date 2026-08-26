from types import SimpleNamespace

import pytest

from app.broker_reconciliation_service import BrokerReconciliationService, ReconciliationConfig
from app.order_lifecycle import OrderLifecycle


class Adapter:
    def __init__(self, orders, positions):
        self._orders = orders
        self._positions = positions

    def get_account(self):
        return {"healthy": True, "authenticated": True}

    def get_orders(self):
        return self._orders

    def get_positions(self):
        return self._positions


class Router:
    def __init__(self, adapter):
        self.adapter = adapter
        self.route = SimpleNamespace(
            adapter=adapter,
            broker_account_id="acct-1",
            generation=4,
        )

    def route_lifecycle_lock(self):
        from contextlib import nullcontext
        return nullcontext()

    def get(self, route):
        return self.route


def test_position_mismatch_blocks_unlock():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("local-1", 10, 100)

    router = Router(Adapter([], [{"symbol": "NIFTY", "quantity": 5, "side": "BUY"}]))
    service = BrokerReconciliationService(
        router,
        ReconciliationConfig(route="live", account_id="acct-1", generation=4),
        lifecycle=lifecycle,
    )

    with pytest.raises(RuntimeError, match="RECONCILIATION_MISMATCH"):
        service.reconcile()


def test_matching_state_can_produce_verified_result():
    lifecycle = OrderLifecycle()
    lifecycle.create("local-1", "NIFTY", "BUY", 10)
    lifecycle.apply_fill("local-1", 10, 100)

    router = Router(Adapter([], [{"symbol": "NIFTY", "quantity": 10, "side": "BUY"}]))
    service = BrokerReconciliationService(
        router,
        ReconciliationConfig(route="live", account_id="acct-1", generation=4),
        lifecycle=lifecycle,
    )

    result = service.reconcile()
    assert result.verified is True
