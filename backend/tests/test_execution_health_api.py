from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


HEALTH_TOKEN = "dev-execution-health-token"


def make_client(*, token: str | None = HEALTH_TOKEN):
    resources = create_resources(
        execution_path=":memory:",
        idempotency_path=":memory:",
        safety_path=":memory:",
        audit_path=":memory:",
        execution_health_token=token,
    )
    resources.execution_observability.increment("submissions", 3)
    resources.execution_observability.increment("submitted", 2)
    resources.execution_observability.increment("quarantined", 1)
    resources.execution_observability.observe_latency("broker_latency", 125)
    return TestClient(create_app(resources=resources))


def test_execution_health_endpoint_exposes_shared_metrics():
    client = make_client()
    response = client.get(
        "/execution/health",
        headers={"X-Execution-Health-Token": HEALTH_TOKEN},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["submissions"] == 3
    assert payload["submitted"] == 2
    assert payload["quarantined"] == 1
    assert payload["broker_average_latency_ms"] == 125.0
    assert payload["quarantine_rate"] == 1 / 3


def test_execution_health_endpoint_requires_authentication():
    response = make_client().get("/execution/health")
    assert response.status_code == 401


def test_execution_health_endpoint_rejects_wrong_token():
    response = make_client().get(
        "/execution/health",
        headers={"X-Execution-Health-Token": "wrong-token"},
    )
    assert response.status_code == 401


def test_execution_health_endpoint_fails_closed_when_token_is_unconfigured():
    response = make_client(token=None).get(
        "/execution/health",
        headers={"X-Execution-Health-Token": HEALTH_TOKEN},
    )
    assert response.status_code == 503
