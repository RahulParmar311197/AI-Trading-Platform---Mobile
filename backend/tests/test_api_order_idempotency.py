from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.app_factory import create_app, create_resources
from app.broker_adapter import BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.models import User


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
    db_path = tmp_path / "orders.sqlite3"
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
        database_url=f"sqlite:///{db_path}",
    )
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="test@example.com", password_hash="test-hash"))
        db.commit()

    broker = CountingBroker()
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)

    with TestClient(app) as client:
        payload = {"user_id": 1, "symbol": "NIFTY", "side": "BUY", "quantity": 1, "order_type": "MARKET"}
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
