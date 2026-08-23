from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources
from app.broker_adapter import BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter


class CountingBroker:
    def __init__(self):
        self.submit_calls = 0

    def submit_order(self, request):
        self.submit_calls += 1
        return BrokerOrderUpdate(order_id="TEST-BROKER-1", status="FILLED", price=100.0)

    def cancel_order(self, order_id):
        return BrokerOrderUpdate(order_id=order_id, status="CANCELLED")

    def get_order(self, order_id):
        return {"order_id": order_id, "status": "FILLED", "price": 100.0}

    def get_orders(self):
        return []

    def get_positions(self):
        return []

    def get_account(self):
        return {}


def test_same_idempotency_key_returns_same_order(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
    )
    resources.safety_store.clear()
    broker = CountingBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)
    client = TestClient(app)
    payload = {
        "user_id": 1,
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
    }
    headers = {"Idempotency-Key": "api-test-123"}

    first = client.post("/api/orders", json=payload, headers=headers)
    second = client.post("/api/orders", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["client_order_id"] == "api-test-123"
    assert second.json()["broker_order_id"] == first.json()["broker_order_id"]
    assert second.json()["message"] == "IDEMPOTENT_REPLAY"
    assert broker.submit_calls == 1
