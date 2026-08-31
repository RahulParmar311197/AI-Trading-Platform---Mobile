from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter


def test_router_keeps_opaque_account_ids_distinct():
    router = BrokerRouter([BrokerRoute("r", PaperBrokerAdapter(), broker_account_id="001", generation="g")], "r")
    request = BrokerOrderRequest("c", "NIFTY", "BUY", 1, broker_account_id="1", broker_route="r", broker_route_generation="g")
    try:
        router._require_account_binding(request, router.get("r"))
    except RuntimeError as exc:
        assert "does not match broker route" in str(exc)
    else:
        raise AssertionError("account ids 001 and 1 must not alias")


def test_router_normalizes_route_account_id_to_string():
    route = BrokerRoute("r", PaperBrokerAdapter(), broker_account_id=7, generation="g")
    assert route.broker_account_id == "7"
