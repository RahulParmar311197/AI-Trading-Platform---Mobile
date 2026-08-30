from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.operational_api import create_operational_router
from app.system_health import TradingSystemHealth


def make_client(health: TradingSystemHealth) -> TestClient:
    app = FastAPI()
    app.include_router(create_operational_router(health=health))
    return TestClient(app)


def test_live_is_200():
    response = make_client(TradingSystemHealth()).get("/health/live")
    assert response.status_code == 200
    assert response.json()["live"] is True


def test_ready_is_503_without_checks():
    response = make_client(TradingSystemHealth()).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_ready_is_503_when_a_check_is_unhealthy():
    health = TradingSystemHealth()
    health.record("database", False, "database unavailable")

    response = make_client(health).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_ready_is_200_when_all_checks_are_healthy():
    health = TradingSystemHealth()
    health.record("database", True)
    health.record("broker", True)

    response = make_client(health).get("/health/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True
