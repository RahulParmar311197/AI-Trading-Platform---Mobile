from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.app_factory import create_app, create_resources
from app.broker_adapter import BrokerOrderUpdate
from app.models import Order, User


class CountingBroker:
    def __init__(self):
        self._lock = Lock()
        self._submit_calls = 0
        self.orders = []
        self.fail_after_accept = False
        self.hide_accepted_orders = False

    @property
    def submit_calls(self):
        with self._lock:
            return self._submit_calls

    def submit_order(self, request):
        with self._lock:
            self._submit_calls += 1
            self.orders.append({"order_id": "TEST-BROKER-1", "client_order_id": request.client_order_id, "status": "FILLED", "price": 100.0})
            if self.fail_after_accept:
                self.fail_after_accept = False
                raise RuntimeError("broker response lost after acceptance")
        return BrokerOrderUpdate(order_id="TEST-BROKER-1", status="FILLED", price=100.0)

    def cancel_order(self, order_id):
        return BrokerOrderUpdate(order_id=order_id, status="CANCELLED")

    def get_order(self, order_id):
        with self._lock:
            return next((order for order in self.orders if order["order_id"] == order_id), None)

    def get_orders(self):
        with self._lock:
            if self.hide_accepted_orders:
                return []
            return list(self.orders)

    def find_order_by_client_id(self, client_order_id):
        with self._lock:
            return next((dict(order) for order in self.orders if order["client_order_id"] == client_order_id), None)

    def get_positions(self):
        return []

    def get_account(self):
        return {}


def test_same_idempotency_key_returns_same_order(tmp_path):
    db_path = tmp_path / "orders.sqlite3"
    resources = create_resources(execution_path=str(tmp_path / "execution.json"), idempotency_path=str(tmp_path / "idempotency.sqlite3"), safety_path=str(tmp_path / "safety.json"), database_url=f"sqlite:///{db_path}")
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="test@example.com", password_hash="test-hash"))
        db.commit()
    broker = CountingBroker()
    from app.broker_router import BrokerRoute, BrokerRouter
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


def test_concurrent_same_idempotency_key_creates_one_order(tmp_path):
    resources = create_resources(execution_path=str(tmp_path / "execution.json"), idempotency_path=str(tmp_path / "idempotency.sqlite3"), safety_path=str(tmp_path / "safety.json"), database_url=f"sqlite:///{tmp_path / 'orders.sqlite3'}")
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="concurrent@example.com", password_hash="test-hash"))
        db.commit()
    broker = CountingBroker()
    from app.broker_router import BrokerRoute, BrokerRouter
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)
    payload = {"user_id": 1, "symbol": "NIFTY", "side": "BUY", "quantity": 1, "order_type": "MARKET"}
    headers = {"Idempotency-Key": "concurrent-api-test"}
    def submit():
        with TestClient(app) as client:
            return client.post("/api/orders", json=payload, headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    assert len({response.json()["broker_order_id"] for response in responses}) == 1
    assert broker.submit_calls == 1
    with Session(resources.session_local()) as db:
        assert db.query(Order).filter(Order.client_order_id == "concurrent-api-test").count() == 1


def test_broker_accepts_then_response_is_lost_retry_recovers_without_resubmit(tmp_path):
    resources = create_resources(execution_path=str(tmp_path / "execution.json"), idempotency_path=str(tmp_path / "idempotency.sqlite3"), safety_path=str(tmp_path / "safety.json"), database_url=f"sqlite:///{tmp_path / 'orders.sqlite3'}")
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="recovery@example.com", password_hash="test-hash"))
        db.commit()
    broker = CountingBroker()
    broker.fail_after_accept = True
    from app.broker_router import BrokerRoute, BrokerRouter
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)
    payload = {"user_id": 1, "symbol": "NIFTY", "side": "BUY", "quantity": 1, "order_type": "MARKET"}
    headers = {"Idempotency-Key": "recovery-api-test"}
    with TestClient(app) as client:
        first = client.post("/api/orders", json=payload, headers=headers)
        retry = client.post("/api/orders", json=payload, headers=headers)
    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["broker_order_id"] == "TEST-BROKER-1"
    assert retry.json()["message"] in {"BROKER_ORDER_RECOVERED", "IDEMPOTENT_REPLAY"}
    assert broker.submit_calls == 1


def test_uncertain_execution_is_202_then_retry_recovers_without_resubmit(tmp_path):
    resources = create_resources(execution_path=str(tmp_path / "execution.json"), idempotency_path=str(tmp_path / "idempotency.sqlite3"), safety_path=str(tmp_path / "safety.json"), database_url=f"sqlite:///{tmp_path / 'orders.sqlite3'}")
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="pending@example.com", password_hash="test-hash"))
        db.commit()
    broker = CountingBroker()
    broker.fail_after_accept = True
    broker.hide_accepted_orders = True
    from app.broker_router import BrokerRoute, BrokerRouter
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)
    payload = {"user_id": 1, "symbol": "NIFTY", "side": "BUY", "quantity": 1, "order_type": "MARKET"}
    headers = {"Idempotency-Key": "pending-api-test"}
    with TestClient(app) as client:
        first = client.post("/api/orders", json=payload, headers=headers)
        assert first.status_code == 202
        assert first.json()["status"] == "PENDING_RECONCILIATION"
        broker.hide_accepted_orders = False
        retry = client.post("/api/orders", json=payload, headers=headers)
    assert retry.status_code == 201
    assert retry.json()["status"] in {"FILLED", "SUBMITTED"}
    assert retry.json()["broker_order_id"] == "TEST-BROKER-1"
    assert retry.json()["message"] in {"BROKER_ORDER_RECOVERED", "IDEMPOTENT_REPLAY"}
    assert broker.submit_calls == 1


def test_broker_adapter_client_order_lookup_is_used_for_reconciliation(tmp_path):
    resources = create_resources(execution_path=str(tmp_path / "execution.json"), idempotency_path=str(tmp_path / "idempotency.sqlite3"), safety_path=str(tmp_path / "safety.json"), database_url=f"sqlite:///{tmp_path / 'orders.sqlite3'}")
    resources.safety_store.clear()
    with Session(resources.session_local()) as db:
        db.add(User(email="lookup@example.com", password_hash="test-hash"))
        db.commit()
    broker = CountingBroker()
    broker.fail_after_accept = True
    broker.hide_accepted_orders = True
    from app.broker_router import BrokerRoute, BrokerRouter
    router = BrokerRouter([BrokerRoute("test", broker)], "test", safety_store=resources.safety_store)
    app = create_app(resources, broker_router=router)
    payload = {"user_id": 1, "symbol": "NIFTY", "side": "BUY", "quantity": 1, "order_type": "MARKET"}
    headers = {"Idempotency-Key": "native-lookup-test"}
    with TestClient(app) as client:
        first = client.post("/api/orders", json=payload, headers=headers)
        assert first.status_code == 201
        assert first.json()["broker_order_id"] == "TEST-BROKER-1"
        assert first.json()["message"] == "BROKER_ORDER_RECOVERED"
    assert broker.submit_calls == 1
