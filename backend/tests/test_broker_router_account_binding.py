import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


def test_account_bound_route_requires_request_account_identity(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter(
        [BrokerRoute("live", PaperBrokerAdapter(), broker_account_id=7, generation="g1")],
        "live",
        safety_store=store,
    )
    request = BrokerOrderRequest("c1", "NIFTY", "BUY", 1, broker_route="live")
    with pytest.raises(RuntimeError, match="broker account identity is required"):
        router.submit(request)


def test_unbound_route_rejects_explicit_account_identity(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter(
        [BrokerRoute("paper", PaperBrokerAdapter())],
        "paper",
        safety_store=store,
    )
    request = BrokerOrderRequest("c1", "NIFTY", "BUY", 1, broker_account_id=7)
    with pytest.raises(RuntimeError, match="route is not account-bound"):
        router.submit(request)
