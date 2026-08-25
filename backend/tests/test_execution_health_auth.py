from fastapi.testclient import TestClient

from app.app_factory import create_app, create_resources


def test_execution_health_requires_token():
    resources = create_resources(execution_path=":memory:", idempotency_path=":memory:", safety_path=":memory:", audit_path=":memory:")
    app = create_app(resources=resources)
    app.state.execution_health_token = "test-secret"
    client = TestClient(app)

    assert client.get("/execution/health").status_code == 401
    assert client.get("/execution/health", headers={"X-Execution-Health-Token": "wrong"}).status_code == 401
    response = client.get("/execution/health", headers={"X-Execution-Health-Token": "test-secret"})
    assert response.status_code == 200
