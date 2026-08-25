from fastapi.testclient import TestClient

from app.main import app


def test_risk_circuit_breaker_lifecycle():
    with TestClient(app) as client:
        state = client.get("/risk/circuit-breaker")
        assert state.status_code == 200
        assert state.json()["can_trade"] is True

        engaged = client.post(
            "/risk/circuit-breaker/engage",
            json={"reason": "integration test halt"},
        )
        assert engaged.status_code == 200
        assert engaged.json()["blocked"] is True
        assert engaged.json()["can_trade"] is False

        blocked = client.get("/risk/circuit-breaker")
        assert blocked.json()["blocked"] is True

        unauthorized = client.post(
            "/risk/circuit-breaker/reset",
            json={"reason": "wrong confirmation"},
        )
        assert unauthorized.status_code == 403
        assert client.get("/risk/circuit-breaker").json()["blocked"] is True

        reset = client.post(
            "/risk/circuit-breaker/reset",
            json={"reason": "authorized reset"},
        )
        assert reset.status_code == 200
        assert reset.json()["blocked"] is False
        assert reset.json()["can_trade"] is True
