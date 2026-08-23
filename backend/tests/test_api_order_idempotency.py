import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.skip(reason="requires configured test database and broker fixtures")
def test_same_idempotency_key_returns_same_order():
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
    assert second.json()["broker_order_id"] == first.json()["broker_order_id"]
