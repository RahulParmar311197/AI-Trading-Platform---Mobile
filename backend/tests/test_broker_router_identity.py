import pytest

from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter


class DuplicateOrderAdapter(BrokerAdapter):
    def submit_order(self, order):
        return BrokerOrderUpdate(order_id="x", status="NEW")

    def cancel_order(self, broker_order_id):
        raise NotImplementedError

    def get_order(self, broker_order_id):
        raise NotImplementedError

    def get_orders(self):
        return [
            {"order_id": "B1", "client_order_id": "same", "status": "OPEN"},
            {"order_id": "B2", "client_order_id": "same", "status": "OPEN"},
        ]

    def get_positions(self):
        return []

    def get_account(self):
        return {"status": "READY"}


def test_ambiguous_client_id_fails_closed():
    router = BrokerRouter([BrokerRoute("paper", DuplicateOrderAdapter())], "paper")
    with pytest.raises(RuntimeError, match="ambiguous broker order identity"):
        router.find_order_by_client_id("same")


def test_unique_client_id_is_recovered():
    class UniqueAdapter(DuplicateOrderAdapter):
        def get_orders(self):
            return [{"order_id": "B1", "client_order_id": "same", "status": "OPEN"}]

    router = BrokerRouter([BrokerRoute("paper", UniqueAdapter())], "paper")
    recovered = router.find_order_by_client_id("same")
    assert recovered["order_id"] == "B1"


def test_unknown_client_id_returns_none():
    router = BrokerRouter([BrokerRoute("paper", DuplicateOrderAdapter())], "paper")
    assert router.find_order_by_client_id("missing") is None
