from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


def test_same_idempotency_key_returns_same_order(tmp_path):
    resources = create_resources(
        execution_path=str(tmp_path / "execution.json"),
        idempotency_path=str(tmp_path / "idempotency.sqlite3"),
        safety_path=str(tmp_path / "safety.json"),
    )
    resources.safety_store.clear()
    app = create_app(resources)
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
