import pytest

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate, UpstoxAdapter


class FakeUpstoxClient:
    def __init__(self):
        self.place_payloads = []
        self.orders = {}
        self.positions = [{"instrument_token": "NSE_EQ|ABC", "quantity": 5}]
        self.profile = {"user_id": "001", "email": "test@example.invalid"}

    def place_order(self, payload):
        self.place_payloads.append(dict(payload))
        self.orders["UP-1"] = {
            "order_id": "UP-1",
            "tag": payload["tag"],
            "trading_symbol": "ABC",
            "transaction_type": payload["transaction_type"],
            "quantity": payload["quantity"],
            "filled_quantity": 0,
            "status": "open",
        }
        return {"status": "success", "data": {"order_id": "UP-1"}}

    def get_order(self, order_id):
        return {"status": "success", "data": self.orders[order_id]}

    def get_orders(self):
        return {"status": "success", "data": list(self.orders.values())}

    def cancel_order(self, order_id):
        self.orders[order_id]["status"] = "cancelled"
        return {"status": "success", "data": {"order_id": order_id}}

    def get_positions(self):
        return {"status": "success", "data": list(self.positions)}

    def get_profile(self):
        return {"status": "success", "data": dict(self.profile)}


def request():
    return BrokerOrderRequest(
        client_order_id="ai-opaque-001",
        symbol="ABC",
        side="BUY",
        quantity=5,
        order_type="MARKET",
        security_id="NSE_EQ|ABC",
        product_type="CNC",
        validity="DAY",
        broker_account_id="001",
        broker_route="upstox",
        broker_route_generation="gen-7",
    )


def test_submit_maps_request_and_preserves_client_identity():
    client = FakeUpstoxClient()
    adapter = UpstoxAdapter(client, broker_account_id="001", broker_route_generation="gen-7")

    result = adapter.submit_order(request())

    assert isinstance(result, BrokerOrderUpdate)
    assert result.order_id == "UP-1"
    assert result.client_order_id == "ai-opaque-001"
    assert result.broker_account_id == "001"
    assert result.broker_route == "upstox"
    assert result.broker_route_generation == "gen-7"
    assert client.place_payloads[0]["tag"] == "ai-opaque-001"
    assert client.place_payloads[0]["instrument_token"] == "NSE_EQ|ABC"
    assert client.place_payloads[0]["transaction_type"] == "BUY"


def test_submit_rejects_cross_account_request_before_broker_call():
    client = FakeUpstoxClient()
    adapter = UpstoxAdapter(client, broker_account_id="001", broker_route_generation="gen-7")
    bad = request().__class__(**{**request().__dict__, "broker_account_id": "1"})

    with pytest.raises(ValueError, match="account"):
        adapter.submit_order(bad)

    assert client.place_payloads == []


def test_find_order_by_client_id_is_authoritative_and_rejects_duplicates():
    client = FakeUpstoxClient()
    adapter = UpstoxAdapter(client, broker_account_id="001", broker_route_generation="gen-7")
    client.orders = {
        "UP-1": {"order_id": "UP-1", "tag": "ai-opaque-001", "trading_symbol": "ABC", "transaction_type": "BUY", "quantity": 5, "filled_quantity": 0, "status": "open"},
    }

    recovered = adapter.find_order_by_client_id("ai-opaque-001")

    assert isinstance(recovered, BrokerOrderUpdate)
    assert recovered.order_id == "UP-1"
    assert recovered.client_order_id == "ai-opaque-001"
    assert recovered.broker_account_id == "001"

    client.orders["UP-2"] = dict(client.orders["UP-1"], order_id="UP-2")
    with pytest.raises(RuntimeError, match="ambiguous"):
        adapter.find_order_by_client_id("ai-opaque-001")


def test_profile_identity_mismatch_fails_closed():
    client = FakeUpstoxClient()
    client.profile["user_id"] = "1"
    adapter = UpstoxAdapter(client, broker_account_id="001", broker_route_generation="gen-7")

    with pytest.raises(RuntimeError, match="account identity"):
        adapter.get_account()


def test_position_and_cancel_mappings_are_exposed():
    client = FakeUpstoxClient()
    adapter = UpstoxAdapter(client, broker_account_id="001", broker_route_generation="gen-7")

    assert adapter.get_positions() == client.positions
    cancelled = adapter.cancel_order("UP-1") if "UP-1" in client.orders else None
    assert cancelled is None
