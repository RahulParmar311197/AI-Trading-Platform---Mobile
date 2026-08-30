from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


def make_client():
    resources = create_resources(
        execution_path=":memory:",
        idempotency_path=":memory:",
        safety_path=":memory:",
        audit_path=":memory:",
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
        headers={"X-Execution-Health-Token": "dev-execution-health-token"},
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
